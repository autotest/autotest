#!/usr/bin/python

import unittest
import common
from autotest_lib.client.common_lib.test_utils import mock
from autotest_lib.server import source_kernel, autotest, hosts


class TestSourceKernel(unittest.TestCase):
    def setUp(self):
        self.god = mock.mock_god()
        self.host = self.god.create_mock_class(hosts.RemoteHost, "host")
        self.god.stub_class(source_kernel.autotest, "Autotest")
        self.kernel_autotest = source_kernel.autotest.Autotest.expect_new()
        self.k = "kernel"
        self.source_kernel = source_kernel.SourceKernel(self.k)

        # call configure to set config_file
        self.config = "config_file"
        self.source_kernel.configure(self.config)


    def tearDown(self):
        self.god.unstub_all()


    def test_install(self):
        # setup
        ctlfile = ("testkernel = job.kernel('%s')\n"
                   "testkernel.install()\n"
                   "testkernel.add_to_bootloader()\n" %(self.k))

        # record
        self.kernel_autotest.install.expect_call(self.host)
        self.host.get_tmp_dir.expect_call().and_return("tmpdir")
        self.kernel_autotest.run.expect_call(ctlfile, "tmpdir", self.host)

        # run and check
        self.source_kernel.install(self.host)
        self.god.check_playback()


    def test_build(self):
        # setup
        patches = "patches"
        self.source_kernel.patch(patches)
        ctlfile = ("testkernel = job.kernel('%s')\n"
                   "testkernel.patch('%s')\n"
                   "testkernel.config('%s')\n"
                   "testkernel.build()\n" % (self.k, patches, self.config))

        # record
        self.host.get_tmp_dir.expect_call().and_return("tmpdir")
        self.kernel_autotest.run.expect_call(ctlfile, "tmpdir", self.host)

        # run and check
        self.source_kernel.build(self.host)
        self.god.check_playback()


if __name__ == "__main__":
    unittest.main()
