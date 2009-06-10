__author__ = """Copyright Martin J. Bligh, 2006,
                Copyright IBM Corp. 2006, Ryan Harper <ryanh@us.ibm.com>"""

import os, shutil, copy, pickle, re, glob
from autotest_lib.client.bin import kernel, kernel_config, os_dep, test
from autotest_lib.client.bin import utils


class xen(kernel.kernel):

    def log(self, msg):
        print msg
        self.logfile.write('%s\n' % msg)


    def __init__(self, job, base_tree, results_dir, tmp_dir, build_dir,
                                        leave = False, kjob = None):
        # call base-class
        kernel.kernel.__init__(self, job, base_tree, results_dir,
                                        tmp_dir, build_dir, leave)
        self.kjob = kjob


    def config(self, config_file, config_list = None):
        raise NotImplementedError('config() not implemented for xen')


    def build(self, make_opts = '', logfile = '', extraversion='autotest'):
        """build xen

        make_opts
                additional options to make, if any
        """
        self.log('running build')
        os_dep.commands('gcc', 'make')
        # build xen with extraversion flag
        os.environ['XEN_EXTRAVERSION'] = '-unstable-%s'% extraversion
        if logfile == '':
            logfile = os.path.join(self.log_dir, 'xen_build')
        os.chdir(self.build_dir)
        self.log('log_dir: %s ' % self.log_dir)
        self.job.logging.tee_redirect_debug_dir(self.log_dir, log_name=logfile)

        # build xen hypervisor and user-space tools
        targets = ['xen', 'tools']
        threads = 2 * utils.count_cpus()
        for t in targets:
            build_string = 'make -j %d %s %s' % (threads, make_opts, t)
            self.log('build_string: %s' % build_string)
            utils.system(build_string)

        # make a kernel job out of the kernel from the xen src if one isn't provided
        if self.kjob is None:
            # get xen kernel tree ready
            self.log("prep-ing xen'ified kernel source tree")
            utils.system('make prep-kernels')

            v = self.get_xen_kernel_build_ver()
            self.log('building xen kernel version: %s' % v)

            # build xen-ified kernel in xen tree
            kernel_base_tree = os.path.join(self.build_dir, \
                    'linux-%s' % self.get_xen_kernel_build_ver())

            self.log('kernel_base_tree = %s' % kernel_base_tree)
            # fix up XENGUEST value in EXTRAVERSION; we can't have
            # files with '$(XENGEUST)' in the name, =(
            self.fix_up_xen_kernel_makefile(kernel_base_tree)

            # make the kernel job
            self.kjob = self.job.kernel(kernel_base_tree)

            # hardcoding dom0 config (no modules for testing, yay!)
            # FIXME: probe host to determine which config to pick
            c = self.build_dir + '/buildconfigs/linux-defconfig_xen0_x86_32'
            self.log('using kernel config: %s ' % c)
            self.kjob.config(c)

            # Xen's kernel tree sucks; doesn't use bzImage, but vmlinux
            self.kjob.set_build_target('vmlinuz')

            # also, the vmlinuz is not out in arch/*/boot, ARGH! more hackery
            self.kjob.set_build_image(self.job.tmpdir + '/build/linux/vmlinuz')

        self.kjob.build()

        self.job.logging.restore()

        xen_version = self.get_xen_build_ver()
        self.log('BUILD VERSION: Xen: %s Kernel:%s' % \
                        (xen_version, self.kjob.get_kernel_build_ver()))


    def build_timed(self, *args, **kwds):
        raise NotImplementedError('build_timed() not implemented')


    def install(self, tag='', prefix = '/', extraversion='autotest'):
        """make install in the kernel tree"""
        self.log('Installing ...')

        os.chdir(self.build_dir)

        if not os.path.isdir(prefix):
            os.mkdir(prefix)
        self.boot_dir = os.path.join(prefix, 'boot')
        if not os.path.isdir(self.boot_dir):
            os.mkdir(self.boot_dir)

        # remember what we are going to install
        xen_version = '%s-%s' % (self.get_xen_build_ver(), extraversion)
        self.xen_image = self.boot_dir + '/xen-' + xen_version + '.gz'
        self.xen_syms  = self.boot_dir + '/xen-syms-' + xen_version

        self.log('Installing Xen ...')
        os.environ['XEN_EXTRAVERSION'] = '-unstable-%s'% extraversion

        # install xen
        utils.system('make DESTDIR=%s -C xen install' % prefix)

        # install tools
        utils.system('make DESTDIR=%s -C tools install' % prefix)

        # install kernel
        ktag = self.kjob.get_kernel_build_ver()
        kprefix = prefix
        self.kjob.install(tag=ktag, prefix=kprefix)


    def add_to_bootloader(self, tag='autotest', args=''):
        """ add this kernel to bootloader, taking an
            optional parameter of space separated parameters
            e.g.:  kernel.add_to_bootloader('mykernel', 'ro acpi=off')
        """

        # turn on xen mode
        self.job.bootloader.enable_xen_mode()

        # remove existing entry if present
        self.job.bootloader.remove_kernel(tag)

        # add xen and xen kernel
        self.job.bootloader.add_kernel(self.kjob.image, tag,
                                       self.kjob.initrd, self.xen_image)

        # if no args passed, populate from /proc/cmdline
        if not args:
            args = open('/proc/cmdline', 'r').readline().strip()

        # add args to entry one at a time
        for a in args.split(' '):
            self.job.bootloader.add_args(tag, a)

        # turn off xen mode
        self.job.bootloader.disable_xen_mode()


    def get_xen_kernel_build_ver(self):
        """Check xen buildconfig for current kernel version"""
        version = patchlevel = sublevel = ''
        extraversion = localversion = ''

        version_file = self.build_dir + '/buildconfigs/mk.linux-2.6-xen'

        for line in open(version_file, 'r').readlines():
            if line.startswith('LINUX_VER'):
                start = line.index('=') + 1
                version = line[start:].strip() + "-xen"
                break

        return version


    def fix_up_xen_kernel_makefile(self, kernel_dir):
        """Fix up broken EXTRAVERSION in xen-ified Linux kernel Makefile"""
        xenguest = ''
        makefile = kernel_dir + '/Makefile'

        for line in open(makefile, 'r').readlines():
            if line.startswith('XENGUEST'):
                start = line.index('=') + 1
                xenguest = line[start:].strip()
                break;

        # change out $XENGUEST in EXTRAVERSION line
        utils.system('sed -i.old "s,\$(XENGUEST),%s," %s' % (xenguest,
                                                             makefile))


    def get_xen_build_ver(self):
        """Check Makefile and .config to return kernel version"""
        version = patchlevel = sublevel = ''
        extraversion = localversion = ''

        for line in open(self.build_dir + '/xen/Makefile', 'r').readlines():
            if line.startswith('export XEN_VERSION'):
                start = line.index('=') + 1
                version = line[start:].strip()
            if line.startswith('export XEN_SUBVERSION'):
                start = line.index('=') + 1
                sublevel = line[start:].strip()
            if line.startswith('export XEN_EXTRAVERSION'):
                start = line.index('=') + 1
                extraversion = line[start:].strip()

        return "%s.%s%s" % (version, sublevel, extraversion)
