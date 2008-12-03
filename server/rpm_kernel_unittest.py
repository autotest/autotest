#!/usr/bin/python

import unittest, os
import common
from autotest_lib.client.common_lib import utils as common_utils
from autotest_lib.client.common_lib.test_utils import mock
from autotest_lib.server import rpm_kernel, utils, hosts
from autotest_lib.server.hosts import bootloader


class TestRpmKernel(unittest.TestCase):
    def setUp(self):
        self.god = mock.mock_god()
        self.kernel = rpm_kernel.RPMKernel()
        self.god.stub_function(utils, "run")
        self.kernel.source_material = "source.rpm"


    def tearDown(self):
        self.god.unstub_all()


    def test_install(self):
        host = self.god.create_mock_class(hosts.RemoteHost, "host")
        host.bootloader = self.god.create_mock_class(bootloader.Bootloader,
                                                     "bootloader")
        self.god.stub_function(self.kernel, "get_image_name")
        self.god.stub_function(self.kernel, "get_vmlinux_name")
        rpm = self.kernel.source_material
        rpm_package = "package.rpm"

        # record
        remote_tmpdir = 'remote_tmp_dir'
        host.get_tmp_dir.expect_call().and_return(remote_tmpdir)
        remote_rpm = os.path.join(remote_tmpdir, os.path.basename(rpm))
        result = common_utils.CmdResult()
        result.exit_status = 0
        result.stdout = rpm_package
        utils.run.expect_call('/usr/bin/rpm -q -p %s' % rpm).and_return(result)
        self.kernel.get_image_name.expect_call().and_return("vmlinuz")
        host.send_file.expect_call(rpm, remote_rpm)
        host.run.expect_call('rpm -e ' + rpm_package, ignore_status = True)
        host.run.expect_call('rpm --force -i ' + remote_rpm)
        self.kernel.get_vmlinux_name.expect_call().and_return("/boot/vmlinux")
        host.run.expect_call('cd /;rpm2cpio %s | cpio -imuv ./boot/vmlinux' %
                             remote_rpm)
        host.run.expect_call('ls /boot/vmlinux')
        host.bootloader.remove_kernel.expect_call('autotest')
        host.bootloader.add_kernel.expect_call("vmlinuz", 'autotest',
                                               args='', default=False)
        host.bootloader.boot_once.expect_call('autotest')

        # run and test
        self.kernel.install(host)
        self.god.check_playback()


    def test_get_version(self):
        # record
        result = common_utils.CmdResult()
        result.exit_status = 0
        result.stdout = "image"

        cmd = ('rpm -qpi %s | grep Version | awk \'{print($3);}\'' %
               (utils.sh_escape("source.rpm")))
        utils.run.expect_call(cmd).and_return(result)

        # run and test
        self.assertEquals(self.kernel.get_version(), result.stdout)
        self.god.check_playback()


    def test_get_image_name(self):
        # record
        result = common_utils.CmdResult()
        result.exit_status = 0
        result.stdout = "image"
        utils.run.expect_call('rpm -q -l -p source.rpm | grep /boot/vmlinuz'
            ).and_return(result)

        # run and test
        self.assertEquals(self.kernel.get_image_name(), result.stdout)
        self.god.check_playback()


    def test_get_vmlinux_name(self):
        # record
        result = common_utils.CmdResult()
        result.exit_status = 0
        result.stdout = "vmlinuz"
        utils.run.expect_call('rpm -q -l -p source.rpm | grep /boot/vmlinux'
            ).and_return(result)

        # run and test
        self.assertEquals(self.kernel.get_vmlinux_name(), result.stdout)
        self.god.check_playback()


    def test_get_initrd_name(self):
        # record
        result = common_utils.CmdResult()
        result.exit_status = 0
        utils.run.expect_call('rpm -q -l -p %s | grep /boot/initrd'
            % "source.rpm", ignore_status=True).and_return(result)

        # run and test
        self.kernel.get_initrd_name()
        self.god.check_playback()


if __name__ == "__main__":
    unittest.main()
