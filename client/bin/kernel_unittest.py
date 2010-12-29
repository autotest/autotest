#!/usr/bin/python

import unittest, os, time, re, glob, logging
import common
from autotest_lib.client.common_lib.test_utils import mock
from autotest_lib.client.bin import kernel, job, utils, kernelexpand
from autotest_lib.client.bin import kernel_config, boottool, os_dep


class TestAddKernelToBootLoader(unittest.TestCase):

    def add_to_bootloader(self, base_args, args, bootloader_args,
                          bootloader_root, tag='image', image='image',
                          initrd='initrd'):
        god = mock.mock_god()
        bootloader = god.create_mock_class(boottool.boottool, "boottool")

        # record
        bootloader.remove_kernel.expect_call(tag)
        bootloader.add_kernel.expect_call(image, tag, initrd=initrd,
                                          args='_dummy_', root=bootloader_root)

        for a in bootloader_args.split():
            bootloader.add_args.expect_call(kernel=tag, args=a)
        bootloader.remove_args.expect_call(kernel=tag, args='_dummy_')

        # run and check
        kernel._add_kernel_to_bootloader(bootloader, base_args, tag, args,
                                         image, initrd)
        god.check_playback()


    def test_add_kernel_to_bootloader(self):
        self.add_to_bootloader(base_args='baseargs', args='',
                               bootloader_args='baseargs', bootloader_root=None)
        self.add_to_bootloader(base_args='arg1 root=/dev/oldroot arg2',
                               args='root=/dev/newroot arg3',
                               bootloader_args='arg1 arg2 arg3',
                               bootloader_root='/dev/newroot')


class TestBootableKernel(unittest.TestCase):

    def setUp(self):
        self.god = mock.mock_god()
        self.god.stub_function(time, "time")
        self.god.stub_function(utils, "system")
        self.god.stub_function(kernel, "_add_kernel_to_bootloader")
        job_ = self.god.create_mock_class(job.job, "job")
        self.kernel = kernel.BootableKernel(job_)
        self.kernel.job.bootloader = self.god.create_mock_class(
                              boottool.boottool, "boottool")


    def tearDown(self):
        # note: time.time() can only be unstubbed via tearDown()
        self.god.unstub_all()


    def boot_kernel(self, ident_check):
        notes = "applied_patches"
        when = 1
        args = ''
        base_args = 'base_args'
        tag = 'ident'
        subdir = 'subdir'
        self.kernel.image = 'image'
        self.kernel.initrd = 'initrd'
        self.kernel.installed_as = tag

        # record
        args_ = args
        if ident_check:
            time.time.expect_call().and_return(when)
            args_ += " IDENT=%d" % when
            status = ["job.end_reboot_and_verify", when, tag, subdir, notes]
        else:
            status = ["job.end_reboot", subdir, tag, notes]
        self.kernel.job.next_step_prepend.expect_call(status)
        self.kernel.job.config_get.expect_call(
                'boot.default_args').and_return(base_args)
        kernel._add_kernel_to_bootloader.expect_call(
                self.kernel.job.bootloader, base_args, tag,
                args_, self.kernel.image, self.kernel.initrd)
        utils.system.expect_call('touch /fastboot')
        self.kernel.job.start_reboot.expect_call()
        self.kernel.job.reboot.expect_call(tag=tag)

        # run and check
        self.kernel._boot_kernel(args=args, ident_check=ident_check,
                                 expected_ident=tag, subdir=subdir, notes=notes)
        self.god.check_playback()


    def test_boot_kernel(self):
        self.boot_kernel(ident_check=False)
        self.boot_kernel(ident_check=True)


class TestKernel(unittest.TestCase):
    def setUp(self):
        self.god = mock.mock_god()

        logging.disable(logging.CRITICAL)

        self.god.stub_function(time, "time")
        self.god.stub_function(os, "mkdir")
        self.god.stub_function(os, "chdir")
        self.god.stub_function(os, "symlink")
        self.god.stub_function(os, "remove")
        self.god.stub_function(os.path, "isdir")
        self.god.stub_function(os.path, "exists")
        self.god.stub_function(os.path, "isfile")
        self.god.stub_function(os_dep, "commands")
        self.god.stub_function(kernel, "open")
        self.god.stub_function(utils, "system")
        self.god.stub_function(utils, "system_output")
        self.god.stub_function(utils, "get_file")
        self.god.stub_function(utils, "get_current_kernel_arch")
        self.god.stub_function(utils, "cat_file_to_cmd")
        self.god.stub_function(utils, "force_copy")
        self.god.stub_function(utils, "extract_tarball_to_dir")
        self.god.stub_function(utils, "count_cpus")
        self.god.stub_function(utils, "get_os_vendor")
        self.god.stub_function(kernelexpand, "expand_classic")
        self.god.stub_function(kernel_config, "modules_needed")
        self.god.stub_function(glob, "glob")
        def dummy_mark(filename, msg):
            pass
        self.god.stub_with(kernel, '_mark', dummy_mark)

        self.job = self.god.create_mock_class(job.job, "job")
        self.job.bootloader = self.god.create_mock_class(boottool.boottool,
                                                         "boottool")

        class DummyLoggingManager(object):
            def tee_redirect_debug_dir(self, *args, **kwargs):
                pass


            def restore(self, *args, **kwargs):
                pass

        self.job.logging = DummyLoggingManager()

        self.job.autodir = "autodir"
        self.base_tree = "2.6.24"
        self.tmp_dir = "tmpdir"
        self.subdir = "subdir"


    def tearDown(self):
        self.god.unstub_all()


    def construct_kernel(self):
        self.kernel = kernel.kernel.__new__(kernel.kernel)
        self.god.stub_function(self.kernel, "extract")

        # setup
        self.src_dir    = os.path.join(self.tmp_dir, 'src')
        self.build_dir  = os.path.join(self.tmp_dir, "build_dir")
        self.config_dir = os.path.join(self.subdir, 'config')
        self.log_dir    = os.path.join(self.subdir, 'debug')
        self.results_dir = os.path.join(self.subdir, 'results')

        # record
        os.path.isdir.expect_call(self.src_dir).and_return(True)
        utils.system.expect_call('rm -rf ' + self.src_dir)
        os.path.isdir.expect_call(self.build_dir).and_return(True)
        utils.system.expect_call('rm -rf ' + self.build_dir)
        os.path.exists.expect_call(self.src_dir).and_return(False)
        os.mkdir.expect_call(self.src_dir)
        for path in [self.config_dir, self.log_dir, self.results_dir]:
            os.path.exists.expect_call(path).and_return(True)
            utils.system.expect_call('rm -rf ' + path)
            os.mkdir.expect_call(path)

        logpath = os.path.join(self.log_dir, 'build_log')
        self.logfile = self.god.create_mock_class(file, "file")
        kernel.open.expect_call(logpath, 'w+').and_return(self.logfile)
        utils.get_current_kernel_arch.expect_call().and_return('ia64')
        self.logfile.write.expect_call('BASE: %s\n' % self.base_tree)
        self.kernel.extract.expect_call(self.base_tree)

        # finish creation of kernel object and test (and unstub extract)
        self.kernel.__init__(self.job, self.base_tree, self.subdir,
                             self.tmp_dir, "build_dir")
        self.god.check_playback()
        self.god.unstub(self.kernel, "extract")


    def test_constructor(self):
        self.construct_kernel()


    def test_kernelexpand1(self):
        self.construct_kernel()

        ret_val = self.kernel.kernelexpand("/path/to/kernel")
        self.assertEquals(ret_val, ["/path/to/kernel"])
        self.god.check_playback()


    def test_kernel_expand2(self):
        self.construct_kernel()
        kernel = "kernel.tar.gz"

        # record
        self.job.config_get.expect_call('mirror.mirrors').and_return('mirror')
        kernelexpand.expand_classic.expect_call(kernel,
            'mirror').and_return('patches')

        # run
        self.assertEquals(self.kernel.kernelexpand(kernel), 'patches')
        self.god.check_playback()


    def test_kernel_expand3(self):
        self.construct_kernel()
        kernel = "kernel.tar.gz"

        # record
        self.job.config_get.expect_call('mirror.mirrors')
        self.job.config_get.expect_call(
            'mirror.ftp_kernel_org').and_return('mirror')
        korg = 'http://www.kernel.org/pub/linux/kernel'
        mirrors = [
                   [ korg + '/v2.6', 'mirror' + '/v2.6' ],
                   [ korg + '/people/akpm/patches/2.6', 'mirror' + '/akpm' ],
                   [ korg + '/people/mbligh', 'mirror' + '/mbligh' ],
                  ]
        kernelexpand.expand_classic.expect_call(kernel,
            mirrors).and_return('patches')

        # run
        self.assertEquals(self.kernel.kernelexpand(kernel), 'patches')
        self.god.check_playback()


    def test_extract1(self):
        self.construct_kernel()

        # setup
        self.god.stub_function(self.kernel, "get_kernel_tree")

        # record
        os.path.exists.expect_call(self.base_tree).and_return(True)
        self.kernel.get_kernel_tree.expect_call(self.base_tree)
        self.job.record.expect_call('GOOD', self.subdir, 'kernel.extract')

        # run
        self.kernel.extract(self.base_tree)
        self.god.check_playback()
        self.god.unstub(self.kernel, "get_kernel_tree")


    def test_extract2(self):
        self.construct_kernel()

        # setup
        self.god.stub_function(self.kernel, "kernelexpand")
        self.god.stub_function(self.kernel, "get_kernel_tree")
        self.god.stub_function(self.kernel, "patch")

        # record
        os.path.exists.expect_call(self.base_tree).and_return(False)
        components = ["component0", "component1"]
        self.kernel.kernelexpand.expect_call(self.base_tree).and_return(
            components)
        self.kernel.get_kernel_tree.expect_call(components[0])
        self.kernel.patch.expect_call(components[1])
        self.job.record.expect_call('GOOD', self.subdir, 'kernel.extract')

        # run
        self.kernel.extract(self.base_tree)
        self.god.check_playback()
        self.god.unstub(self.kernel, "kernelexpand")
        self.god.unstub(self.kernel, "get_kernel_tree")
        self.god.unstub(self.kernel, "patch")


    def test_patch1(self):
        self.construct_kernel()
        patches = ('patch1', 'patch2')
        self.god.stub_function(self.kernel, "apply_patches")
        self.god.stub_function(self.kernel, "get_patches")

        #record
        self.kernel.get_patches.expect_call(patches).and_return(patches)
        self.kernel.apply_patches.expect_call(patches)
        self.job.record.expect_call('GOOD', self.subdir, 'kernel.patch')

        #run
        self.kernel.patch(*patches)
        self.god.check_playback()
        self.god.unstub(self.kernel, "apply_patches")
        self.god.unstub(self.kernel, "get_patches")


    def test_patch2(self):
        self.construct_kernel()
        patches = []

        # record
        self.job.record.expect_call('GOOD', self.subdir, 'kernel.patch')

        # run
        self.kernel.patch(*patches)
        self.god.check_playback()


    def test_config(self):
        self.construct_kernel()

        # setup
        self.god.stub_function(self.kernel, "set_cross_cc")
        self.god.stub_class(kernel_config, "kernel_config")

        # record
        self.kernel.set_cross_cc.expect_call()
        kernel_config.kernel_config.expect_new(self.job, self.build_dir,
                                               self.config_dir, '', None,
                                               False, self.base_tree, None)
        self.job.record.expect_call('GOOD', self.subdir, 'kernel.config')

        # run
        self.kernel.config()
        self.god.check_playback()
        self.god.unstub(self.kernel, "set_cross_cc")


    def test_get_patches(self):
        self.construct_kernel()

        # setup
        patches = ['patch1', 'patch2', 'patch3']
        local_patches = []

        # record
        for patch in patches:
            dest = os.path.join(self.src_dir, os.path.basename(patch))
            utils.get_file.expect_call(patch, dest)
            utils.system_output.expect_call(
                'md5sum ' + dest).and_return('md5sum')
            local_patches.append((patch, dest, 'md5sum'))

        # run and check
        self.assertEquals(self.kernel.get_patches(patches), local_patches)
        self.god.check_playback()


    def test_apply_patches(self):
        self.construct_kernel()

        # setup
        patches = []
        patches.append(('patch1', 'patch1.gz', 'md5sum1'))
        patches.append(('patch2', 'patch2.bz2', 'md5sum2'))
        patches.append(('patch3', 'patch3', 'md5sum3'))
        applied_patches = []

        # record
        os.chdir.expect_call(self.build_dir)

        patch_id = "%s %s %s" % ('patch1', 'patch1', 'md5sum1')
        log = "PATCH: " + patch_id + "\n"
        utils.cat_file_to_cmd.expect_call('patch1.gz',
            'patch -p1 > /dev/null')
        self.logfile.write.expect_call(log)
        applied_patches.append(patch_id)

        patch_id = "%s %s %s" % ('patch2', 'patch2', 'md5sum2')
        log = "PATCH: " + patch_id + "\n"
        utils.cat_file_to_cmd.expect_call('patch2.bz2',
            'patch -p1 > /dev/null')
        self.logfile.write.expect_call(log)
        applied_patches.append(patch_id)

        utils.force_copy.expect_call('patch3',
            self.results_dir).and_return('local_patch3')
        self.job.relative_path.expect_call('local_patch3').and_return(
            'rel_local_patch3')
        patch_id = "%s %s %s" % ('patch3', 'rel_local_patch3', 'md5sum3')
        log = "PATCH: " + patch_id + "\n"
        utils.cat_file_to_cmd.expect_call('patch3',
            'patch -p1 > /dev/null')
        self.logfile.write.expect_call(log)
        applied_patches.append(patch_id)

        # run and test
        self.kernel.apply_patches(patches)
        self.assertEquals(self.kernel.applied_patches, applied_patches)
        self.god.check_playback()


    def test_get_kernel_tree1(self):
        self.construct_kernel()

        # record
        os.path.isdir.expect_call(self.base_tree).and_return(True)
        os.symlink.expect_call(self.base_tree, self.build_dir)

        # run and check
        self.kernel.get_kernel_tree(self.base_tree)
        self.god.check_playback()


    def test_get_kernel_tree2(self):
        self.construct_kernel()

        # record
        os.path.isdir.expect_call(self.base_tree).and_return(False)
        os.chdir.expect_call(os.path.dirname(self.src_dir))
        tarball = os.path.join(self.src_dir, os.path.basename(self.base_tree))
        utils.get_file.expect_call(self.base_tree, tarball)
        utils.extract_tarball_to_dir.expect_call(tarball,
                                                          self.build_dir)

        # run and check
        self.kernel.get_kernel_tree(self.base_tree)
        self.god.check_playback()


    def test_extraversion(self):
        self.construct_kernel()
        tag = "tag"
        # setup
        self.god.stub_function(self.kernel, "config")

        # record
        os.chdir.expect_call(self.build_dir)
        extraversion_sub = r's/^CONFIG_LOCALVERSION=\s*"\(.*\)"/CONFIG_LOCALVERSION='
        cfg = self.build_dir + '/.config'
        p = extraversion_sub + '"\\1-%s"/' % tag
        utils.system.expect_call('mv %s %s.old' % (cfg, cfg))
        utils.system.expect_call("sed '%s' < %s.old > %s" % (p, cfg, cfg))
        self.kernel.config.expect_call(make='oldconfig')

        # run and check
        self.kernel.extraversion(tag)
        self.god.check_playback()


    def test_build(self):
        self.construct_kernel()
        self.god.stub_function(self.kernel, "extraversion")
        self.god.stub_function(self.kernel, "set_cross_cc")
        self.god.stub_function(self.kernel, "get_kernel_build_ver")
        self.kernel.build_target = 'build_target'

        # record
        os_dep.commands.expect_call('gcc', 'make')
        logfile = os.path.join(self.log_dir, 'kernel_build')
        os.chdir.expect_call(self.build_dir)
        self.kernel.extraversion.expect_call('autotest')
        self.kernel.set_cross_cc.expect_call()
        utils.system.expect_call('make dep', ignore_status=True)
        utils.count_cpus.expect_call().and_return(4)
        threads = 2 * 4
        build_string = 'make -j %d %s %s' % (threads, '', 'build_target')
        utils.system.expect_call(build_string)
        kernel_config.modules_needed.expect_call('.config').and_return(True)
        utils.system.expect_call('make -j %d modules' % (threads))
        self.kernel.get_kernel_build_ver.expect_call().and_return('2.6.24')
        kernel_version = re.sub('-autotest', '', '2.6.24')
        self.logfile.write.expect_call('BUILD VERSION: %s\n' % kernel_version)
        utils.force_copy.expect_call(self.build_dir+'/System.map',
                                              self.results_dir)
        self.job.record.expect_call('GOOD', self.subdir, 'kernel.build')

        # run and check
        self.kernel.build()
        self.god.check_playback()


    def test_build_timed(self):
        self.construct_kernel()
        self.god.stub_function(self.kernel, "set_cross_cc")
        self.god.stub_function(self.kernel, "clean")

        # record
        os.chdir.expect_call(self.build_dir)
        self.kernel.set_cross_cc.expect_call()
        self.kernel.clean.expect_call()
        build_string = "/usr/bin/time -o /dev/null make  -j 8 vmlinux"
        build_string += ' > /dev/null 2>&1'
        utils.system.expect_call(build_string)
        os.path.isfile.expect_call('vmlinux').and_return(True)

        # run and check
        self.kernel.build_timed(threads=8)
        self.god.check_playback()


    def test_clean(self):
        self.construct_kernel()

        # record
        os.chdir.expect_call(self.build_dir)
        utils.system.expect_call('make clean > /dev/null 2> /dev/null')
        self.job.record.expect_call('GOOD', self.subdir, 'kernel.clean')

        # run and check
        self.kernel.clean()
        self.god.check_playback()


    def test_mkinitrd(self):
        self.construct_kernel()

        # record
        utils.get_os_vendor.expect_call().and_return('Ubuntu')
        os.path.isfile.expect_call('initrd').and_return(True)
        os.remove.expect_call('initrd')
        self.job.config_get.expect_call(
            'kernel.mkinitrd_extra_args').and_return(None)
        args = ''
        glob.glob.expect_call('/lib/modules/2.6.24*').and_return(['2.6.24'])
        os.path.isfile.expect_call('/usr/sbin/mkinitrd').and_return(True)
        cmd = '/usr/sbin/mkinitrd'
        utils.system.expect_call('%s %s -o initrd 2.6.24' % (cmd, args))
        self.job.record.expect_call('GOOD', self.subdir, 'kernel.mkinitrd')

        # run and check
        self.kernel.mkinitrd(version="2.6.24", image="image",
                             system_map="system_map", initrd="initrd")
        self.god.check_playback()


    def test_install(self):
        self.construct_kernel()
        tag = 'autotest'
        prefix = '/'
        self.kernel.build_image = None
        self.kernel.build_target = 'build_target'
        self.god.stub_function(self.kernel, "get_kernel_build_ver")
        self.god.stub_function(self.kernel, "mkinitrd")

        # record
        os.chdir.expect_call(self.build_dir)
        os.path.isdir.expect_call(prefix).and_return(False)
        os.mkdir.expect_call(prefix)
        boot_dir = os.path.join(prefix, 'boot')
        os.path.isdir.expect_call(boot_dir).and_return(False)
        os.mkdir.expect_call(boot_dir)
        glob.glob.expect_call(
            'arch/*/boot/' + 'build_target').and_return('')
        build_image = self.kernel.build_target
        utils.force_copy.expect_call('vmlinux',
            '/boot/vmlinux-autotest')
        utils.force_copy.expect_call('build_target',
            '/boot/vmlinuz-autotest')
        utils.force_copy.expect_call('System.map',
            '/boot/System.map-autotest')
        utils.force_copy.expect_call('.config',
            '/boot/config-autotest')
        kernel_config.modules_needed.expect_call('.config').and_return(True)
        utils.system.expect_call('make modules_install INSTALL_MOD_PATH=%s'
                                 % prefix)
        initrd = boot_dir + '/initrd-' + tag
        self.kernel.get_kernel_build_ver.expect_call().and_return('2.6.24')
        self.kernel.mkinitrd.expect_call('2.6.24', '/boot/vmlinuz-autotest',
            '/boot/System.map-autotest', '/boot/initrd-autotest')
        self.job.record.expect_call('GOOD', self.subdir, 'kernel.install')

        # run and check
        self.kernel.install()
        self.god.check_playback()


    def test_get_kernel_build_arch1(self):
        self.construct_kernel()

        # record
        utils.get_current_kernel_arch.expect_call().and_return("i386")

        # run and check
        self.assertEquals(self.kernel.get_kernel_build_arch(), "i386")
        self.god.check_playback()


    def test_get_kernel_build_arch2(self):
        self.construct_kernel()

        # run and check
        self.assertEquals(self.kernel.get_kernel_build_arch('i586'), "i386")
        self.god.check_playback()


    def test_get_kernel_build_release(self):
        self.construct_kernel()
        mock_file = self.god.create_mock_class(file, "file")

        # record
        for f in [self.build_dir + "/include/linux/version.h",
                  self.build_dir + "/include/linux/utsrelease.h"]:
            os.path.exists.expect_call(f).and_return(True)
            kernel.open.expect_call(f, 'r').and_return(mock_file)
            mock_file.readlines.expect_call().and_return("Some lines")
            mock_file.close.expect_call()

        for f in [self.build_dir + "/include/linux/compile.h",
                  self.build_dir + "/include/generated/utsrelease.h",
                  self.build_dir + "/include/generated/compile.h"]:
            os.path.exists.expect_call(f).and_return(False)

        # run and test
        self.kernel.get_kernel_build_release()
        self.god.check_playback()


    def test_get_kernel_build_ident(self):
        self.construct_kernel()
        self.god.stub_function(self.kernel, "get_kernel_build_release")

        # record
        self.kernel.get_kernel_build_release.expect_call().and_return(
            ("AwesomeRelease", "1.0"))

        # run and check
        self.assertEquals(self.kernel.get_kernel_build_ident(),
            "AwesomeRelease::1.0")
        self.god.check_playback()


    def test_boot(self):
        self.construct_kernel()
        self.god.stub_function(self.kernel, "get_kernel_build_ident")
        self.god.stub_function(self.kernel, "install")
        self.god.stub_function(self.kernel, "_boot_kernel")
        self.kernel.applied_patches = "applied_patches"
        self.kernel.installed_as = None
        args = ''
        expected_ident = 'ident'
        ident = True

        # record
        self.kernel.install.expect_call()
        self.kernel.get_kernel_build_ident.expect_call(
                ).and_return(expected_ident)
        self.kernel._boot_kernel.expect_call(
                args, ident, expected_ident,
                self.subdir, self.kernel.applied_patches)

        # run and check
        self.kernel.boot(args=args, ident=ident)
        self.god.check_playback()


if __name__ == "__main__":
    unittest.main()
