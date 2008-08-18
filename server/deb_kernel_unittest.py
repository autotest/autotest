#!/usr/bin/python

import unittest, os
import common
from autotest_lib.client.common_lib.test_utils import mock
from autotest_lib.client.common_lib import utils as common_utils
from autotest_lib.server import deb_kernel, utils, hosts
from autotest_lib.server.hosts import bootloader


class TestDebKernel(unittest.TestCase):
    def setUp(self):
        self.god = mock.mock_god()
        self.kernel = deb_kernel.DEBKernel()
        self.host = self.god.create_mock_class(hosts.RemoteHost, "host")
        self.host.bootloader = self.god.create_mock_class(
            bootloader.Bootloader, "bootloader")
        self.god.stub_function(utils, "run")


    def tearDown(self):
        self.god.unstub_all()


    def common_code(self):
        self.kernel.source_material = "source.rpm"
        basename = os.path.basename(self.kernel.source_material)
        self.remote_tmpdir = "remote/tmp/dir"
        self.remote_filename = os.path.join(self.remote_tmpdir, basename)
        self.host.get_tmp_dir.expect_call().and_return(self.remote_tmpdir)
        self.host.send_file.expect_call(self.kernel.source_material,
                                        self.remote_filename)


    def test_install(self):
        self.common_code()

        # record
        self.host.run.expect_call('dpkg -i "%s"' %
                                 (utils.sh_escape(self.remote_filename)))

        result = common_utils.CmdResult()
        result.stdout = "1"
        utils.run.expect_call('dpkg-deb -f "%s" version' %
                utils.sh_escape(self.kernel.source_material)).and_return(result)
        utils.run.expect_call('dpkg-deb -f "%s" version' %
                utils.sh_escape(self.kernel.source_material)).and_return(result)
        self.host.run.expect_call('mkinitramfs -o "/boot/initrd.img-1" "1"')

        utils.run.expect_call('dpkg-deb -f "%s" version' %
                utils.sh_escape(self.kernel.source_material)).and_return(result)
        utils.run.expect_call('dpkg-deb -f "%s" version' %
                utils.sh_escape(self.kernel.source_material)).and_return(result)
        self.host.bootloader.add_kernel.expect_call('/boot/vmlinuz-1',
                                                    initrd='/boot/initrd.img-1')

        # run and check
        self.kernel.install(self.host)
        self.god.check_playback()


    def test_extract(self):
        # setup
        self.common_code()
        content_dir= os.path.join(self.remote_tmpdir, "contents")

        # record
        self.host.run.expect_call('dpkg -x "%s" "%s"' %
                                  (utils.sh_escape(self.remote_filename),
                                   utils.sh_escape(content_dir)))

        # run and test
        self.kernel.extract(self.host)
        self.god.check_playback()


if __name__ == "__main__":
    unittest.main()
