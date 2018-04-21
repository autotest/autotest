import copy
import glob
import logging
import os
import pickle
import re
import shutil
import time

from autotest.client import kernel_config, os_dep, kernelexpand
from autotest.client import utils
from autotest.client.shared import log, error, distro


def tee_output_logdir_mark(fn):
    def tee_logdir_mark_wrapper(self, *args, **dargs):
        mark = self.__class__.__name__ + "." + fn.__name__
        logging.info("--- START %s ---", mark)
        self.job.logging.tee_redirect_debug_dir(self.log_dir)
        try:
            result = fn(self, *args, **dargs)
        finally:
            self.job.logging.restore()
            logging.info("--- END %s ---", mark)

        return result

    tee_logdir_mark_wrapper.__name__ = fn.__name__
    return tee_logdir_mark_wrapper


def _add_kernel_to_bootloader(bootloader, base_args, tag, args, image, initrd):
    """
    Add a kernel with the specified tag to the boot config using the given
    bootloader object. Also process the base_args and args kernel arguments
    by removing all root= options and give the last root= option value to
    the bootloader as a root device.

    :param bootloader: bootloader object
    :param base_args: base cmdline kernel arguments
    :param tag: kernel tag
    :param args: kernel cmdline arguments that are merged with base_args; a
            root= option in "args" will override any from base_args
    :param image: kernel image file
    :param initrd: initrd file
    """
    # remove existing entry if present
    bootloader.remove_kernel(tag)

    if base_args:
        if args:
            args = '%s %s' % (base_args, args)
        else:
            args = base_args

    bootloader.add_kernel(path=image, title=tag, initrd=initrd, args=args)


class BootableKernel(object):

    def __init__(self, job):
        self.job = job
        self.installed_as = None  # kernel choice in bootloader menu
        self.image = None
        self.initrd = ''

    def _boot_kernel(self, args, ident_check, expected_ident, subdir, notes):
        """
        Boot a kernel, with post-boot kernel id check

        :param args:  kernel cmdline arguments
        :param ident_check: check kernel id after boot
        :param expected_ident:
        :param subdir: job-step qualifier in status log
        :param notes:  additional comment in status log
        """
        # If we can check the kernel identity do so.
        if ident_check:
            when = int(time.time())
            args += " IDENT=%d" % when
            self.job.next_step_prepend(["job.end_reboot_and_verify", when,
                                        expected_ident, subdir, notes])
        else:
            self.job.next_step_prepend(["job.end_reboot", subdir,
                                        expected_ident, notes])

        self.add_to_bootloader(args)

        # defer fsck for next reboot, to avoid reboots back to default kernel
        utils.system('touch /fastboot')  # this file is removed automatically

        # Boot it.
        self.job.start_reboot()
        self.job.reboot(tag=self.installed_as)

    def add_to_bootloader(self, args=''):
        # Point bootloader to the selected tag.
        _add_kernel_to_bootloader(self.job.bootloader,
                                  self.job.config_get('boot.default_args'),
                                  self.installed_as, args, self.image,
                                  self.initrd)


class kernel(BootableKernel):

    """ Class for compiling kernels.

    Data for the object includes the src files
    used to create the kernel, patches applied, config (base + changes),
    the build directory itself, and logged output

    Properties:
            job
                    Backpointer to the job object we're part of
            autodir
                    Path to the top level autotest dir (see global_config.ini,
                    session COMMON/autotest_top_path)
            src_dir
                    <tmp_dir>/src/
            build_dir
                    <tmp_dir>/linux/
            config_dir
                    <results_dir>/config/
            log_dir
                    <results_dir>/debug/
            results_dir
                    <results_dir>/results/
    """

    autodir = ''

    def __init__(self, job, base_tree, subdir, tmp_dir, build_dir, leave=False):
        """Initialize the kernel build environment

        job
                which job this build is part of
        base_tree
                base kernel tree. Can be one of the following:
                        1. A local tarball
                        2. A URL to a tarball
                        3. A local directory (will symlink it)
                        4. A shorthand expandable (eg '2.6.11-git3')
        subdir
                subdir in the results directory (eg "build")
                (holds config/, debug/, results/)
        tmp_dir

        leave
                Boolean, whether to leave existing tmpdir or not
        """
        super(kernel, self).__init__(job)
        self.autodir = job.autodir

        self.src_dir = os.path.join(tmp_dir, 'src')
        self.build_dir = os.path.join(tmp_dir, build_dir)
        # created by get_kernel_tree
        self.config_dir = os.path.join(subdir, 'config')
        self.log_dir = os.path.join(subdir, 'debug')
        self.results_dir = os.path.join(subdir, 'results')
        self.subdir = os.path.basename(subdir)

        if not leave:
            if os.path.isdir(self.src_dir):
                utils.system('rm -rf ' + self.src_dir)
            if os.path.isdir(self.build_dir):
                utils.system('rm -rf ' + self.build_dir)

        if not os.path.exists(self.src_dir):
            os.mkdir(self.src_dir)
        for path in [self.config_dir, self.log_dir, self.results_dir]:
            if os.path.exists(path):
                utils.system('rm -rf ' + path)
            os.mkdir(path)

        logpath = os.path.join(self.log_dir, 'build_log')
        self.logfile = open(logpath, 'w+')
        self.applied_patches = []

        self.target_arch = None
        self.build_target = 'bzImage'
        self.build_image = None

        arch = utils.get_current_kernel_arch()
        if arch == 'ia64':
            self.build_target = 'all'
            self.build_image = 'vmlinux.gz'
        elif arch in ['s390', 's390x']:
            self.build_target = 'image'
        elif 'ppc' in arch:
            self.build_target = 'vmlinux'

        if not leave:
            self.logfile.write('BASE: %s\n' % base_tree)

            # Where we have direct version hint record that
            # for later configuration selection.
            shorthand = re.compile(r'^\d+\.\d+\.\d+')
            if shorthand.match(base_tree):
                self.base_tree_version = base_tree
            else:
                self.base_tree_version = None

            # Actually extract the tree.  Make sure we know it occurred
            self.extract(base_tree)

    def kernelexpand(self, kernel):
        # If we have something like a path, just use it as it is
        if '/' in kernel:
            return [kernel]

        # Find the configured mirror list.
        mirrors = self.job.config_get('mirror.mirrors')
        if not mirrors:
            # LEGACY: convert the kernel.org mirror
            mirror = self.job.config_get('mirror.ftp_kernel_org')
            if mirror:
                korg = 'http://www.kernel.org/pub/linux/kernel'
                mirrors = [
                    [korg + '/v2.6', mirror + '/v2.6'],
                    [korg + '/people/akpm/patches/2.6', mirror + '/akpm'],
                    [korg + '/people/mbligh', mirror + '/mbligh'],
                ]

        patches = kernelexpand.expand_classic(kernel, mirrors)
        print(patches)

        return patches

    @log.record
    @tee_output_logdir_mark
    def extract(self, base_tree):
        if os.path.exists(base_tree):
            self.get_kernel_tree(base_tree)
        else:
            base_components = self.kernelexpand(base_tree)
            print('kernelexpand: ')
            print(base_components)
            self.get_kernel_tree(base_components.pop(0))
            if base_components:      # apply remaining patches
                self.patch(*base_components)

    @log.record
    @tee_output_logdir_mark
    def patch(self, *patches):
        """Apply a list of patches (in order)"""
        if not patches:
            return
        print('Applying patches: ', patches)
        self.apply_patches(self.get_patches(patches))

    @log.record
    @tee_output_logdir_mark
    def config(self, config_file='', config_list=None, defconfig=False,
               make=None):
        self.set_cross_cc()
        config = kernel_config.kernel_config(self.job, self.build_dir,
                                             self.config_dir,
                                             config_file, config_list,
                                             defconfig, self.base_tree_version,
                                             make)
        if kernel_config.feature_enabled("CONFIG_DEFAULT_UIMAGE",
                                         config.build_config):
            self.build_target = 'uImage'

    def get_patches(self, patches):
        """fetch the patches to the local src_dir"""
        local_patches = []
        for patch in patches:
            dest = os.path.join(self.src_dir, os.path.basename(patch))
            # FIXME: this isn't unique. Append something to it
            # like wget does if it's not there?
            print("get_file %s %s %s %s" % (patch, dest, self.src_dir,
                                            os.path.basename(patch)))
            utils.get_file(patch, dest)
            # probably safer to use the command, not python library
            md5sum = utils.system_output('md5sum ' + dest).split()[0]
            local_patches.append((patch, dest, md5sum))
        return local_patches

    def apply_patches(self, local_patches):
        """apply the list of patches, in order"""
        builddir = self.build_dir
        os.chdir(builddir)

        if not local_patches:
            return None
        for (spec, local, md5sum) in local_patches:
            if local.endswith('.bz2') or local.endswith('.gz'):
                ref = spec
            else:
                ref = utils.force_copy(local, self.results_dir)
                ref = self.job.relative_path(ref)
            patch_id = "%s %s %s" % (spec, ref, md5sum)
            log = "PATCH: " + patch_id + "\n"
            print(log)
            utils.cat_file_to_cmd(local, 'patch -p1 > /dev/null')
            self.logfile.write(log)
            self.applied_patches.append(patch_id)

    def get_kernel_tree(self, base_tree):
        """Extract/link base_tree to self.build_dir"""

        # if base_tree is a dir, assume uncompressed kernel
        if os.path.isdir(base_tree):
            print('Symlinking existing kernel source')
            if os.path.islink(self.build_dir):
                os.remove(self.build_dir)
            os.symlink(base_tree, self.build_dir)

        # otherwise, extract tarball
        else:
            os.chdir(os.path.dirname(self.src_dir))
            # Figure out local destination for tarball
            tarball = os.path.join(self.src_dir, os.path.basename(base_tree.split(';')[0]))
            utils.get_file(base_tree, tarball)
            print('Extracting kernel tarball:', tarball, '...')
            utils.extract_tarball_to_dir(tarball, self.build_dir)

    def extraversion(self, tag, append=True):
        os.chdir(self.build_dir)
        extraversion_sub = r's/^CONFIG_LOCALVERSION=\s*"\(.*\)"/CONFIG_LOCALVERSION='
        cfg = self.build_dir + '/.config'
        if append:
            p = extraversion_sub + '"\\1-%s"/' % tag
        else:
            p = extraversion_sub + '"-%s"/' % tag
        if os.path.exists(cfg):
            utils.system('mv %s %s.old' % (cfg, cfg))
            utils.system("sed '%s' < %s.old > %s" % (p, cfg, cfg))
            self.config(make='oldconfig')
        else:
            self.config()

    @log.record
    @tee_output_logdir_mark
    def build(self, make_opts='', logfile='', extraversion='autotest'):
        """build the kernel

        make_opts
                additional options to make, if any
        """
        os_dep.commands('gcc', 'make')
        if logfile == '':
            logfile = os.path.join(self.log_dir, 'kernel_build')
        os.chdir(self.build_dir)
        if extraversion:
            self.extraversion(extraversion)
        self.set_cross_cc()
        # setup_config_file(config_file, config_overrides)

        # Not needed on 2.6, but hard to tell -- handle failure
        utils.system('make dep', ignore_status=True)
        threads = 2 * utils.count_cpus()
        build_string = 'make -j %d %s %s' % (threads, make_opts,
                                             self.build_target)
        # eg make bzImage, or make zImage
        print(build_string)
        utils.system(build_string)
        if kernel_config.modules_needed('.config'):
            utils.system('make -j %d %s modules' % (threads, make_opts))

        kernel_version = self.get_kernel_build_ver()
        kernel_version = re.sub('-autotest', '', kernel_version)
        self.logfile.write('BUILD VERSION: %s\n' % kernel_version)

        utils.force_copy(self.build_dir + '/System.map', self.results_dir)

    def build_timed(self, threads, timefile='/dev/null', make_opts='',
                    output='/dev/null'):
        """time the bulding of the kernel"""
        os.chdir(self.build_dir)
        self.set_cross_cc()

        self.clean()
        build_string = ("/usr/bin/time -o %s make %s -j %s vmlinux" %
                        (timefile, make_opts, threads))
        build_string += ' > %s 2>&1' % output
        print(build_string)
        utils.system(build_string)

        if (not os.path.isfile('vmlinux')):
            errmsg = "no vmlinux found, kernel build failed"
            raise error.TestError(errmsg)

    @log.record
    @tee_output_logdir_mark
    def clean(self):
        """make clean in the kernel tree"""
        os.chdir(self.build_dir)
        print("make clean")
        utils.system('make clean > /dev/null 2> /dev/null')

    @log.record
    @tee_output_logdir_mark
    def mkinitrd(self, version, image, system_map, initrd):
        """Build kernel initrd image.
        Try to use distro specific way to build initrd image.
        Parameters:
                version
                        new kernel version
                image
                        new kernel image file
                system_map
                        System.map file
                initrd
                        initrd image file to build
        """
        d = distro.detect()

        if os.path.isfile(initrd):
            print("Existing %s file, will remove it." % initrd)
            os.remove(initrd)

        args = self.job.config_get('kernel.mkinitrd_extra_args')

        # don't leak 'None' into mkinitrd command
        if not args:
            args = ''

        # It is important to match the version with a real directory inside
        # /lib/modules
        real_version_list = glob.glob('/lib/modules/%s*' % version)
        rl = len(real_version_list)
        if rl == 0:
            logging.error("No directory %s found under /lib/modules. Initramfs"
                          "creation will most likely fail and your new kernel"
                          "will fail to build", version)
        else:
            if rl > 1:
                logging.warning("Found more than one possible match for "
                                "kernel version %s under /lib/modules", version)
            version = os.path.basename(real_version_list[0])

        if d.name in ['redhat', 'fedora']:
            try:
                cmd = os_dep.command('dracut')
                full_cmd = '%s -f %s %s' % (cmd, initrd, version)
            except ValueError:
                cmd = os_dep.command('mkinitrd')
                full_cmd = '%s %s %s %s' % (cmd, args, initrd, version)
            utils.system(full_cmd)
        elif d.name in ['sles']:
            utils.system('mkinitrd %s -k %s -i %s -M %s' %
                         (args, image, initrd, system_map))
        elif d.name in ['debian', 'ubuntu']:
            if os.path.isfile('/usr/sbin/mkinitrd'):
                cmd = '/usr/sbin/mkinitrd'
            elif os.path.isfile('/usr/sbin/mkinitramfs'):
                cmd = '/usr/sbin/mkinitramfs'
            else:
                raise error.TestError('No Debian initrd builder')
            utils.system('%s %s -o %s %s' % (cmd, args, initrd, version))
        else:
            raise error.TestError('Unsupported distro %s' % d.name)

    def set_build_image(self, image):
        self.build_image = image

    @log.record
    @tee_output_logdir_mark
    def install(self, tag='autotest', prefix='/', install_vmlinux=True):
        """make install in the kernel tree"""

        # Record that we have installed the kernel, and
        # the tag under which we installed it.
        self.installed_as = tag

        os.chdir(self.build_dir)

        if not os.path.isdir(prefix):
            os.mkdir(prefix)
        self.boot_dir = os.path.join(prefix, 'boot')
        if not os.path.isdir(self.boot_dir):
            os.mkdir(self.boot_dir)

        if not self.build_image:
            images = glob.glob('arch/*/boot/' + self.build_target)
            if len(images):
                self.build_image = images[0]
            else:
                self.build_image = self.build_target

        # remember installed files
        self.vmlinux = self.boot_dir + '/vmlinux-' + tag
        if (self.build_image != 'vmlinux'):
            self.image = self.boot_dir + '/vmlinuz-' + tag
        else:
            self.image = self.vmlinux
            install_vmlinux = True
        self.system_map = self.boot_dir + '/System.map-' + tag
        self.config_file = self.boot_dir + '/config-' + tag
        self.initrd = ''

        # copy to boot dir
        if install_vmlinux:
            utils.force_copy('vmlinux', self.vmlinux)
        if (self.build_image != 'vmlinux'):
            utils.force_copy(self.build_image, self.image)
        utils.force_copy('System.map', self.system_map)
        utils.force_copy('.config', self.config_file)

        if not kernel_config.modules_needed('.config'):
            return

        utils.system('make modules_install INSTALL_MOD_PATH=%s' % prefix)
        if prefix == '/':
            self.initrd = self.boot_dir + '/initrd-' + tag
            self.mkinitrd(self.get_kernel_build_ver(), self.image,
                          self.system_map, self.initrd)

    def get_kernel_build_arch(self, arch=None):
        """
        Work out the current kernel architecture (as a kernel arch)
        """
        if not arch:
            arch = utils.get_current_kernel_arch()
        if re.match('i.86', arch):
            return 'i386'
        elif re.match('sun4u', arch):
            return 'sparc64'
        elif re.match('arm.*', arch):
            return 'arm'
        elif re.match('sa110', arch):
            return 'arm'
        elif re.match('s390x', arch):
            return 's390'
        elif re.match('parisc64', arch):
            return 'parisc'
        elif re.match('ppc.*', arch):
            return 'powerpc'
        elif re.match('mips.*', arch):
            return 'mips'
        else:
            return arch

    def get_kernel_build_release(self):
        releasem = re.compile(r'.*UTS_RELEASE\s+"([^"]+)".*')
        versionm = re.compile(r'.*UTS_VERSION\s+"([^"]+)".*')

        release = None
        version = None

        for f in [self.build_dir + "/include/linux/version.h",
                  self.build_dir + "/include/linux/utsrelease.h",
                  self.build_dir + "/include/linux/compile.h",
                  self.build_dir + "/include/generated/utsrelease.h",
                  self.build_dir + "/include/generated/compile.h"]:
            if os.path.exists(f):
                fd = open(f, 'r')
                for line in fd.readlines():
                    m = releasem.match(line)
                    if m:
                        release = m.groups()[0]
                    m = versionm.match(line)
                    if m:
                        version = m.groups()[0]
                fd.close()

        return (release, version)

    def get_kernel_build_ident(self):
        (release, version) = self.get_kernel_build_release()

        if not release or not version:
            raise error.JobError('kernel has no identity')

        return release + '::' + version

    def boot(self, args='', ident=True):
        """ install and boot this kernel, do not care how
            just make it happen.
        """

        # If the kernel has not yet been installed,
        #   install it now as default tag.
        if not self.installed_as:
            self.install()

        expected_ident = self.get_kernel_build_ident()
        self._boot_kernel(args, ident, expected_ident,
                          self.subdir, self.applied_patches)

    def get_kernel_build_ver(self):
        """Check Makefile and .config to return kernel version"""
        version = patchlevel = sublevel = extraversion = localversion = ''

        for line in open(self.build_dir + '/Makefile', 'r').readlines():
            if line.startswith('VERSION'):
                version = line[line.index('=') + 1:].strip()
            if line.startswith('PATCHLEVEL'):
                patchlevel = line[line.index('=') + 1:].strip()
            if line.startswith('SUBLEVEL'):
                sublevel = line[line.index('=') + 1:].strip()
            if line.startswith('EXTRAVERSION'):
                extraversion = line[line.index('=') + 1:].strip()

        for line in open(self.build_dir + '/.config', 'r').readlines():
            if line.startswith('CONFIG_LOCALVERSION='):
                localversion = line.rstrip().split('"')[1]

        return "%s.%s.%s%s%s" % (version, patchlevel, sublevel, extraversion, localversion)

    def set_build_target(self, build_target):
        if build_target:
            self.build_target = build_target
            print('BUILD TARGET: %s' % self.build_target)

    def set_cross_cc(self, target_arch=None, cross_compile=None,
                     build_target='bzImage'):
        """Set up to cross-compile.
                This is broken. We need to work out what the default
                compile produces, and if not, THEN set the cross
                compiler.
        """

        if self.target_arch:
            return

        # if someone has set build_target, don't clobber in set_cross_cc
        # run set_build_target before calling set_cross_cc
        if not self.build_target:
            self.set_build_target(build_target)

        # If no 'target_arch' given assume native compilation
        if target_arch is None:
            target_arch = utils.get_current_kernel_arch()
            if target_arch == 'ppc64':
                if self.build_target == 'bzImage':
                    self.build_target = 'vmlinux'

        if not cross_compile:
            cross_compile = self.job.config_get('kernel.cross_cc')

        if cross_compile:
            os.environ['CROSS_COMPILE'] = cross_compile
        else:
            if 'CROSS_COMPILE' in os.environ:
                del os.environ['CROSS_COMPILE']
        return  # HACK. Crap out for now.

        # At this point I know what arch I *want* to build for
        # but have no way of working out what arch the default
        # compiler DOES build for.

        def install_package(package):
            raise NotImplementedError("I don't exist yet!")

        if target_arch in ['ppc64', 'ppc']:
            install_package('ppc64-cross')
            cross_compile = os.path.join(self.autodir, 'sources/ppc64-cross/bin')

        elif target_arch == 'x86_64':
            install_package('x86_64-cross')
            cross_compile = os.path.join(self.autodir, 'sources/x86_64-cross/bin')

        os.environ['ARCH'] = self.target_arch = target_arch

        self.cross_compile = cross_compile
        if self.cross_compile:
            os.environ['CROSS_COMPILE'] = self.cross_compile

    def pickle_dump(self, filename):
        """dump a pickle of ourself out to the specified filename

        we can't pickle the backreference to job (it contains fd's),
        nor would we want to. Same for logfile (fd's).
        """
        temp = copy.copy(self)
        temp.job = None
        temp.logfile = None
        pickle.dump(temp, open(filename, 'wb'))


class rpm_kernel(BootableKernel):

    """
    Class for installing a binary rpm kernel package
    """
    kernel_string = '/boot/vmlinuz'

    def __init__(self, job, rpm_package, subdir):
        super(rpm_kernel, self).__init__(job)
        self.rpm_package = rpm_package
        self.log_dir = os.path.join(subdir, 'debug')
        self.subdir = os.path.basename(subdir)
        if os.path.exists(self.log_dir):
            utils.system('rm -rf ' + self.log_dir)
        os.mkdir(self.log_dir)

    def build(self, *args, **dargs):
        """
        Dummy function, binary kernel so nothing to build.
        """
        pass

    @log.record
    @tee_output_logdir_mark
    def install(self, tag='autotest', install_vmlinux=True):
        self.installed_as = tag

        self.image = None
        self.initrd = ''
        for rpm_pack in self.rpm_package:
            rpm_name = utils.system_output('rpm -qp ' + rpm_pack)

            # install without dependencies (e.g., kernel-firmware)
            utils.system('rpm -i --force --nodeps ' + rpm_pack)

            # get file list
            files = utils.system_output('rpm -ql ' + rpm_name).splitlines()

            # search for vmlinuz
            for file in files:
                if file.startswith(self.kernel_string):
                    self.full_version = file[len(self.kernel_string + '-'):]
                    self.image = file
                    self.rpm_flavour = rpm_name.split('-')[1]

                    # get version and release number
                    r_cmd = ('rpm --queryformat="%{VERSION}\\n%{RELEASE}\\n" '
                             '-q ' + rpm_name)
                    (self.version,
                     self.release) = utils.system_output(
                        r_cmd).splitlines()[0:2]

                    # prefer /boot/kernel-version before /boot/kernel
                    if self.full_version:
                        break

            # search for initrd
            for file in files:
                if file.startswith('/boot/init'):
                    self.initrd = file
                    # prefer /boot/initrd-version before /boot/initrd
                    if len(file) > len('/boot/initrd'):
                        break

        if self.image is None:
            errmsg = "specified rpm file(s) don't contain /boot/vmlinuz"
            raise error.TestError(errmsg)

        # install vmlinux
        if install_vmlinux:
            for rpm_pack in self.rpm_package:
                vmlinux = utils.system_output(
                    'rpm -q -l -p %s | grep /boot/vmlinux' % rpm_pack)
            utils.system('cd /; rpm2cpio %s | cpio -imuv .%s 2>&1'
                         % (rpm_pack, vmlinux))
            if not os.path.exists(vmlinux):
                raise error.TestError('%s does not exist after installing %s'
                                      % (vmlinux, rpm_pack))

    def boot(self, args='', ident=True):
        """ install and boot this kernel
        """

        # If the kernel has not yet been installed,
        #   install it now as default tag.
        if not self.installed_as:
            self.install()

        expected_ident = self.full_version
        if not expected_ident:
            expected_ident = '-'.join([self.version,
                                       self.rpm_flavour,
                                       self.release])

        self._boot_kernel(args, ident, expected_ident,
                          None, 'rpm')


class srpm_kernel(kernel):
    prefix = '/root/rpmbuild'
    binrpm_pattern = re.compile(r'kernel-[0-9]')

    def __init__(self, job, rpm_package, subdir):
        # download and install src.rpm
        self.job = job
        self.subdir = subdir
        self.SOURCES_dir = os.path.join(self.prefix, 'SOURCES')
        self.SPECS_dir = os.path.join(self.prefix, 'SPECS')
        self.BUILD_dir = os.path.join(self.prefix, 'BUILD')
        self.BUILDROOT_dir = os.path.join(self.prefix, 'BUILDROOT')
        self.RPMS_dir = os.path.join(self.prefix, 'RPMS')
        # technically this is where both patches and tarballs get put, but
        # since we don't have any tarballs, we just fudge it
        self.src_dir = self.SOURCES_dir
        self.spec = os.path.join(self.SPECS_dir, 'kernel.spec')
        self.results_dir = os.path.join(subdir, 'results')
        self.log_dir = os.path.join(subdir, 'debug')
        self.patches = []
        self.configs = []
        self.built = False
        self.finish_init()
        self.__init(rpm_package)

    # dummy function to override in children classes to modify __init__ behavior
    def finish_init(self):
        pass

    def __init(self, rpm_package):

        for path in [self.prefix, self.SOURCES_dir, self.SPECS_dir,
                     self.BUILD_dir, self.BUILDROOT_dir, self.RPMS_dir,
                     self.src_dir, self.results_dir, self.log_dir]:
            utils.system('rm -rf ' + path)
            os.mkdir(path)

        utils.system('rpm -ivh %s' % rpm_package)

    def apply_patches(self, local_patches):
        self.patches += local_patches

    def setup_source(self):
        if len(self.configs) > 0:
            for config_file in glob.glob(os.path.join(self.SOURCES_dir, 'kernel-*%s*' % utils.get_current_kernel_arch())):
                with open(config_file, 'a') as cfg:
                    for config in self.configs:
                        cfg.write("%s\n" % config)

    def consume_one_config(self, config_option):
        if os.path.exists(config_option) or utils.is_url(config_option):
            if os.path.exists(config_option):
                cfg = open(config_option, 'r')
            if utils.is_url(config_option):
                cfg = utils.urlopen(config_option)
            # read the file
            for line in cfg.readlines():
                self.configs.append(line)
        else:
            self.configs.append(config_option)

    def config(self, *args, **kwargs):
        for config_option in args:
            self.consume_one_config(config_option)

    def update_spec_line(self, line, outspec, tag):
        if line.startswith('# % define buildid'):
            outspec.write('%%define buildid .%s\n' % tag)
            return
        if len(self.patches) > 0:
            if line.startswith('Patch999999'):
                for index, (spec, dest, md5sum) in enumerate(self.patches):
                    outspec.write('Patch%d: %s\n' %
                                  (index,
                                   os.path.relpath(dest, self.SOURCES_dir)))
            if line.startswith('ApplyOptionalPatch linux-kernel-test.patch'):
                for (spec, dest, md5sum) in self.patches:
                    outspec.write('ApplyPatch %s\n' %
                                  os.path.relpath(dest, self.SOURCES_dir))
        if len(self.configs) > 0:
            if line.startswith('%define listnewconfig_fail'):
                outspec.write('%define listnewconfig_fail 0\n')
                return
        outspec.write(line)

    def update_spec(self, tag):
        utils.system('cp %s %s' % (self.spec, self.spec + '.bak'))
        with open(self.spec + '.bak', 'r') as inspec:
            with open(self.spec, 'w+') as outspec:
                for line in inspec:
                    self.update_spec_line(line, outspec, tag)

    def prep(self, tag='autotest'):
        self.setup_source()
        self.update_spec(tag)
        utils.system('rpmbuild -bp %s' % self.spec)

    def build(self, tag='autotest'):
        self.setup_source()
        self.update_spec(tag)
        utils.system('rpmbuild -bb %s' % self.spec)
        dest = os.path.join(self.results_dir, "RPMs")
        shutil.copytree(self.RPMS_dir, dest)
        rpms = []
        for root, dirs, files in os.walk(self.RPMS_dir):
            for name in files:
                if self.binrpm_pattern.search(name) is not None:
                    rpms.append(os.path.join(root, name))
        self.binrpms = rpms
        self.built = True

    def install(self, tag='autotest'):
        # install resulting rpm on system
        if not self.built:
            self.build(tag)
        r = rpm_kernel_vendor(self.job, self.binrpms, self.subdir)
        r.install(tag=tag)

    def boot(self, args=''):
        # boot resulting rpm on system
        if not self.built:
            self.build()
        r = rpm_kernel_vendor(self.job, self.binrpms, self.subdir)
        r.boot(args=args)


class rpm_kernel_suse(rpm_kernel):

    """ Class for installing openSUSE/SLE rpm kernel package
    """
    kernel_string = '/boot/vmlinux'

    def install(self):
        # do not set the new kernel as the default one
        os.environ['PBL_AUTOTEST'] = '1'

        rpm_kernel.install(self, 'dummy')
        self.installed_as = self.job.bootloader.get_title_for_kernel(self.image)
        if not self.installed_as:
            errmsg = "cannot find installed kernel in bootloader configuration"
            raise error.TestError(errmsg)

    def add_to_bootloader(self, args=''):
        """ Set parameters of this kernel in bootloader
        """

        # pull the base argument set from the job config
        baseargs = self.job.config_get('boot.default_args')
        if baseargs:
            args = baseargs + ' ' + args

        self.job.bootloader.add_args(self.installed_as, args)


class srpm_kernel_suse(srpm_kernel):
    prefix = '/usr/src/packages'

    def __init__(self, job, rpm_package, subdir):
        # download and install src.rpm
        super(srpm_kernel_suse, self).__init__(job, rpm_package, subdir)
        utils.system('rm -rf ' + self.cfg_dir)
        os.mkdir(self.cfg_dir)
        os.mkdir(os.path.join(self.cfg_dir, utils.get_current_kernel_arch()))

    def finish_init(self):
        self.src_dir = os.path.join(self.SOURCES_dir, 'patches.addon')
        self.cfg_dir = os.path.join(self.SOURCES_dir, 'config.addon')
        d = distro.detect()
        if d.version == '11':
            self.spec = os.path.join(self.SPECS_dir, 'kernel-ppc64.spec')
            self.config_file = os.path.join(self.cfg_dir, utils.get_current_kernel_arch(), utils.get_current_kernel_arch())
            # sles11 needs both kernel and kernel-base
            self.binrpm_pattern = re.compile(r'kernel-%s-(base|[0-9])' % utils.get_current_kernel_arch())
        if d.version == '12':
            self.spec = os.path.join(self.SPECS_dir, 'kernel-default.spec')
            self.config_file = os.path.join(self.cfg_dir, utils.get_current_kernel_arch(), 'default')
            self.binrpm_pattern = re.compile(r'kernel-default-[0-9]')

    def setup_source(self):
        # setup tarball
        if len(self.patches) > 0:
            # need to ensure the tarball's contents are relative to SOURCES
            utils.system('tar jCcf %s %s.tar.bz2 %s' % (self.SOURCES_dir,
                                                        self.src_dir,
                                                        os.path.basename(self.src_dir)))
            # append to series file
            with open(os.path.join(self.SOURCES_dir, 'series.conf'), 'a') as series:
                for (spec, local, md5sum) in self.patches:
                    series.write("%s\n" % os.path.relpath(local, self.SOURCES_dir))

        if len(self.configs) > 0:
            with open(self.config_file, 'w+') as cfg:
                for config in self.configs:
                    cfg.write("%s\n" % config)
            # need to ensure the tarball's contents are relative to SOURCES
            utils.system('tar jCcf %s %s.tar.bz2 %s' % (self.SOURCES_dir,
                                                        self.cfg_dir,
                                                        os.path.basename(self.cfg_dir)))
            # if we are mucking with the new CONFIG symbols, the build will
            # fail if any dependencies get pulled in
            utils.system('touch /usr/src/packages/SOURCES/TOLERATE-UNKNOWN-NEW-CONFIG-OPTIONS')

        # generate spec file
        cwd = os.getcwd()
        os.chdir(self.SOURCES_dir)
        utils.system('./mkspec')
        os.chdir(cwd)

        # copy spec file
        d = distro.detect()
        if d.version == '11':
            utils.system('cp %s %s' % (
                          os.path.join(self.SOURCES_dir, 'kernel-ppc64.spec'),
                          self.spec))
        else:
            utils.system('cp %s %s' % (
                          os.path.join(self.SOURCES_dir, 'kernel-default.spec'),
                          self.spec))

    def update_spec_line(self, line, outspec, tag):
        if line.startswith('Release'):
            outspec.write('Release:        %s\n' % tag)
            return
        outspec.write(line)


def rpm_kernel_vendor(job, rpm_package, subdir):
    d = distro.detect()
    if d.name == "sles":
        return rpm_kernel_suse(job, rpm_package, subdir)
    else:
        return rpm_kernel(job, rpm_package, subdir)


def srpm_kernel_vendor(job, rpm_package, subdir):
    d = distro.detect()
    if d.name == "sles":
        return srpm_kernel_suse(job, rpm_package, subdir)
    else:
        return srpm_kernel(job, rpm_package, subdir)


# just make the preprocessor a nop
def _preprocess_path_dummy(path):
    return path.strip()


# pull in some optional site-specific path pre-processing
preprocess_path = utils.import_site_function(__file__,
                                             "autotest.client.site_kernel", "preprocess_path",
                                             _preprocess_path_dummy)


def auto_kernel(job, path, subdir, tmp_dir, build_dir, leave=False):
    """
    Create a kernel object, dynamically selecting the appropriate class to use
    based on the path provided.
    """
    kernel_paths = [preprocess_path(path)]
    if kernel_paths[0].endswith('.list'):
        # Fetch the list of packages to install
        kernel_list = os.path.join(tmp_dir, 'kernel.list')
        utils.get_file(kernel_paths[0], kernel_list)
        kernel_paths = [p.strip() for p in open(kernel_list).readlines()]

    if kernel_paths[0].endswith('.rpm'):
        if kernel_paths[0].endswith('src.rpm') and len(kernel_paths) > 1:
            raise error.TestError("don't know what to do with more than one non-rpm kernel file")
        rpm_paths = []
        for kernel_path in kernel_paths:
            if os.path.exists(kernel_path):
                rpm_paths.append(kernel_path)
            else:
                # Fetch the rpm into the job's packages directory and pass it to
                # rpm_kernel
                rpm_name = os.path.basename(kernel_path)

                # If the preprocessed path (kernel_path) is only a name then
                # search for the kernel in all the repositories, else fetch the
                # kernel from that specific path.
                job.pkgmgr.fetch_pkg(rpm_name, os.path.join(job.pkgdir, rpm_name),
                                     repo_url=os.path.dirname(kernel_path))
                rpm_paths.append(os.path.join(job.pkgdir, rpm_name))
        if kernel_paths[0].endswith('src.rpm'):
            return srpm_kernel_vendor(job, rpm_paths[0], subdir)
        return rpm_kernel_vendor(job, rpm_paths, subdir)
    else:
        if len(kernel_paths) > 1:
            raise error.TestError("don't know what to do with more than one non-rpm kernel file")
        return kernel(job, kernel_paths[0], subdir, tmp_dir, build_dir, leave)
