#!/usr/bin/python

import unittest, os
import common

from autotest_lib.client.common_lib.test_utils import mock
from autotest_lib.client.common_lib import error
from autotest_lib.server import utils, hosts
from autotest_lib.server.hosts import bootloader


class test_bootloader(unittest.TestCase):
    def setUp(self):
        self.god = mock.mock_god()

        # mock out get_server_dir
        self.god.stub_function(utils, "get_server_dir")


    def tearDown(self):
        self.god.unstub_all()


    def create_mock_host(self):
        # useful for building disposable RemoteHost mocks
        return self.god.create_mock_class(hosts.RemoteHost, "host")


    def create_install_boottool_mock(self, loader, dst_dir):
        mock_install_boottool = \
                self.god.create_mock_function("_install_boottool")
        def install_boottool():
            loader._boottool_path = dst_dir
            mock_install_boottool()
        loader._install_boottool = install_boottool
        return mock_install_boottool


    def test_install_fails_without_host(self):
        host = self.create_mock_host()
        loader = bootloader.Bootloader(host)
        del host
        self.assertRaises(error.AutoservError, loader._install_boottool)


    def test_installs_to_tmpdir(self):
        TMPDIR = "/unittest/tmp"
        SERVERDIR = "/unittest/server"
        BOOTTOOL_SRC = os.path.join(SERVERDIR, bootloader.BOOTTOOL_SRC)
        BOOTTOOL_SRC = os.path.abspath(BOOTTOOL_SRC)
        BOOTTOOL_DST = os.path.join(TMPDIR, "boottool")
        # set up the recording
        host = self.create_mock_host()
        host.get_tmp_dir.expect_call().and_return(TMPDIR)
        utils.get_server_dir.expect_call().and_return(SERVERDIR)
        host.send_file.expect_call(BOOTTOOL_SRC, TMPDIR)
        # run the test
        loader = bootloader.Bootloader(host)
        loader._install_boottool()
        # assert the playback is correct
        self.god.check_playback()
        # assert the final dest is correct
        self.assertEquals(loader._boottool_path, BOOTTOOL_DST)


    def test_get_path_automatically_installs(self):
        BOOTTOOL_DST = "/unittest/tmp/boottool"
        host = self.create_mock_host()
        loader = bootloader.Bootloader(host)
        # mock out loader.install_boottool
        mock_install = \
                self.create_install_boottool_mock(loader, BOOTTOOL_DST)
        # set up the recording
        mock_install.expect_call()
        # run the test
        self.assertEquals(loader._get_boottool_path(), BOOTTOOL_DST)
        self.god.check_playback()


    def test_install_is_only_called_once(self):
        BOOTTOOL_DST = "/unittest/tmp/boottool"
        host = self.create_mock_host()
        loader = bootloader.Bootloader(host)
        # mock out loader.install_boottool
        mock_install = \
                self.create_install_boottool_mock(loader, BOOTTOOL_DST)
        # set up the recording
        mock_install.expect_call()
        # run the test
        self.assertEquals(loader._get_boottool_path(), BOOTTOOL_DST)
        self.god.check_playback()
        self.assertEquals(loader._get_boottool_path(), BOOTTOOL_DST)
        self.god.check_playback()


if __name__ == "__main__":
    unittest.main()
