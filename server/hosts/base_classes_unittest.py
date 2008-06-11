#!/usr/bin/python

import unittest
import common

from autotest_lib.client.common_lib import global_config
from autotest_lib.client.common_lib.test_utils import mock
from autotest_lib.server import utils
from autotest_lib.server.hosts import base_classes, bootloader


class test_host_class(unittest.TestCase):
    def setUp(self):
        self.god = mock.mock_god()
        # stub out get_server_dir, global_config.get_config_value
        self.god.stub_with(utils, "get_server_dir",
                           lambda: "/unittest/server")
        self.god.stub_function(global_config.global_config,
                               "get_config_value")
        # stub out the bootloader
        self.real_bootloader = bootloader.Bootloader
        bootloader.Bootloader = lambda arg: object()


    def tearDown(self):
        self.god.unstub_all()
        bootloader.Bootloader = self.real_bootloader


    def test_init(self):
        self.god.stub_function(utils, "get_server_dir")
        host = base_classes.Host.__new__(base_classes.Host)
        bootloader.Bootloader = \
                self.god.create_mock_class_obj(self.real_bootloader,
                                               "Bootloader")
        # overwrite this attribute as it's irrelevant for these tests
        # and may cause problems with construction of the mock
        bootloader.Bootloader.boottool_path = None
        # set up the recording
        utils.get_server_dir.expect_call().and_return("/unittest/server")
        bootloader.Bootloader.expect_new(host)
        # run the actual test
        host.__init__()
        self.god.check_playback()


    def test_install(self):
        host = base_classes.Host()
        # create a dummy installable class
        class installable(object):
            def install(self, host):
                pass
        installableObj = self.god.create_mock_class(installable,
                                                    "installableObj")
        installableObj.install.expect_call(host)
        # run the actual test
        host.install(installableObj)
        self.god.check_playback()


    def test_get_wait_up_empty(self):
        global_config.global_config.get_config_value.expect_call(
            "HOSTS", "wait_up_processes", default="").and_return("")

        host = base_classes.Host()
        self.assertEquals(host.get_wait_up_processes(), set())
        self.god.check_playback()


    def test_get_wait_up_ignores_whitespace(self):
        global_config.global_config.get_config_value.expect_call(
            "HOSTS", "wait_up_processes", default="").and_return("  ")

        host = base_classes.Host()
        self.assertEquals(host.get_wait_up_processes(), set())
        self.god.check_playback()


    def test_get_wait_up_single_process(self):
        global_config.global_config.get_config_value.expect_call(
            "HOSTS", "wait_up_processes", default="").and_return("proc1")

        host = base_classes.Host()
        self.assertEquals(host.get_wait_up_processes(),
                          set(["proc1"]))
        self.god.check_playback()


    def test_get_wait_up_multiple_process(self):
        global_config.global_config.get_config_value.expect_call(
            "HOSTS", "wait_up_processes", default="").and_return(
            "proc1,proc2,proc3")

        host = base_classes.Host()
        self.assertEquals(host.get_wait_up_processes(),
                          set(["proc1", "proc2", "proc3"]))
        self.god.check_playback()


    def test_get_wait_up_drops_duplicates(self):
        global_config.global_config.get_config_value.expect_call(
            "HOSTS", "wait_up_processes", default="").and_return(
            "proc1,proc2,proc1")

        host = base_classes.Host()
        self.assertEquals(host.get_wait_up_processes(),
                          set(["proc1", "proc2"]))
        self.god.check_playback()


if __name__ == "__main__":
    unittest.main()
