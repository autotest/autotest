#!/usr/bin/python

import unittest, os
import common

from autotest_lib.client.common_lib.test_utils import mock
from autotest_lib.client.common_lib import error, utils as common_utils
from autotest_lib.server import utils, hosts
from autotest_lib.server.hosts import bootloader


class test_bootloader_install(unittest.TestCase):
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
                self.god.create_mock_function("install_boottool")
        def install_boottool():
            loader._boottool_path = dst_dir
            mock_install_boottool()
        loader.install_boottool = install_boottool
        return mock_install_boottool


    def test_install_fails_without_host(self):
        host = self.create_mock_host()
        loader = bootloader.Bootloader(host)
        del host
        self.assertRaises(error.AutoservError, loader.install_boottool)


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
        loader.install_boottool()
        # assert the playback is correct
        self.god.check_playback()
        # assert the final dest is correct
        self.assertEquals(loader.boottool_path, BOOTTOOL_DST)


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
        self.assertEquals(loader.boottool_path, BOOTTOOL_DST)
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
        self.assertEquals(loader.boottool_path, BOOTTOOL_DST)
        self.god.check_playback()
        self.assertEquals(loader.boottool_path, BOOTTOOL_DST)
        self.god.check_playback()


class test_bootloader_methods(unittest.TestCase):
    def setUp(self):
        self.god = mock.mock_god()
        self.host = self.god.create_mock_class(hosts.RemoteHost, "host")
        # creates a bootloader with _run_boottool mocked out
        self.loader = bootloader.Bootloader(self.host)
        self.god.stub_function(self.loader, "_run_boottool")


    def tearDown(self):
        self.god.unstub_all()


    def expect_run_boottool(self, arg, result):
        result = common_utils.CmdResult(stdout=result, exit_status=0)
        self.loader._run_boottool.expect_call(arg).and_return(result)


    def test_get_type(self):
        # set up the recording
        self.expect_run_boottool("--bootloader-probe", "lilo\n")
        # run the test
        self.assertEquals(self.loader.get_type(), "lilo")
        self.god.check_playback()


    def test_get_arch(self):
        # set up the recording
        self.expect_run_boottool("--arch-probe", "x86_64\n")
        # run the test
        self.assertEquals(self.loader.get_architecture(), "x86_64")
        self.god.check_playback()


    def test_get_default(self):
        # set up the recording
        self.expect_run_boottool("--default", "0\n")
        # run the test
        self.assertEquals(self.loader.get_default(), "0")
        self.god.check_playback()


    def test_get_titles(self):
        # set up the recording
        self.expect_run_boottool(mock.regex_comparator(
            r"^--info all \|"), "title #1\ntitle #2\n")
        # run the test
        self.assertEquals(self.loader.get_titles(),
                          ["title #1", "title #2"])
        self.god.check_playback()


    def test_get_info_single_result(self):
        RESULT = (
        "index\t: 5\n"
        "args\t: ro single\n"
        "boot\t: (hd0,0)\n"
        "initrd\t: /boot/initrd.img-2.6.15-23-386\n"
        "kernel\t: /boot/vmlinuz-2.6.15-23-386\n"
        "root\t: UUID=07D7-0714\n"
        "savedefault\t:   \n"
        "title\t: Distro, kernel 2.6.15-23-386\n"
        )
        # set up the recording
        self.expect_run_boottool("--info=5", RESULT)
        # run the test
        info = self.loader.get_info(5)
        self.god.check_playback()
        expected_info = {"index": "5", "args": "ro single",
                         "boot": "(hd0,0)",
                         "initrd": "/boot/initrd.img-2.6.15-23-386",
                         "kernel": "/boot/vmlinuz-2.6.15-23-386",
                         "root": "UUID=07D7-0714", "savedefault": "",
                         "title": "Distro, kernel 2.6.15-23-386"}
        self.assertEquals(expected_info, info)


    def test_get_info_missing_result(self):
        # set up the recording
        self.expect_run_boottool("--info=4", "")
        # run the test
        info = self.loader.get_info(4)
        self.god.check_playback()
        self.assertEquals({}, info)


    def test_get_info_multiple_results(self):
        RESULT = (
        "index\t: 5\n"
        "args\t: ro single\n"
        "boot\t: (hd0,0)\n"
        "initrd\t: /boot/initrd.img-2.6.15-23-386\n"
        "kernel\t: /boot/vmlinuz-2.6.15-23-386\n"
        "root\t: UUID=07D7-0714\n"
        "savedefault\t:   \n"
        "title\t: Distro, kernel 2.6.15-23-386\n"
        "\n"
        "index\t: 7\n"
        "args\t: ro single\n"
        "boot\t: (hd0,0)\n"
        "initrd\t: /boot/initrd.img-2.6.15-23-686\n"
        "kernel\t: /boot/vmlinuz-2.6.15-23-686\n"
        "root\t: UUID=07D7-0714\n"
        "savedefault\t:   \n"
        "title\t: Distro, kernel 2.6.15-23-686\n"
        )
        # set up the recording
        self.expect_run_boottool("--info=all", RESULT)
        # run the test
        info = self.loader.get_all_info()
        self.god.check_playback()
        expected_info = [{"index": "5", "args": "ro single",
                          "boot": "(hd0,0)",
                          "initrd": "/boot/initrd.img-2.6.15-23-386",
                          "kernel": "/boot/vmlinuz-2.6.15-23-386",
                          "root": "UUID=07D7-0714", "savedefault": "",
                          "title": "Distro, kernel 2.6.15-23-386"},
                         {"index": "7", "args": "ro single",
                          "boot": "(hd0,0)",
                          "initrd": "/boot/initrd.img-2.6.15-23-686",
                          "kernel": "/boot/vmlinuz-2.6.15-23-686",
                          "root": "UUID=07D7-0714", "savedefault": "",
                          "title": "Distro, kernel 2.6.15-23-686"}]
        self.assertEquals(expected_info, info)


    def test_set_default(self):
        # set up the recording
        self.loader._run_boottool.expect_call("--set-default=41")
        # run the test
        self.loader.set_default(41)
        self.god.check_playback()


    def test_add_args(self):
        # set up the recording
        self.loader._run_boottool.expect_call(
            "--update-kernel=10 --args=\"some kernel args\"")
        # run the test
        self.loader.add_args(10, "some kernel args")
        self.god.check_playback()


    def test_remove_args(self):
        # set up the recording
        self.loader._run_boottool.expect_call(
            "--update-kernel=12 --remove-args=\"some kernel args\"")
        # run the test
        self.loader.remove_args(12, "some kernel args")
        self.god.check_playback()


    def test_add_kernel_basic(self):
        self.loader.get_titles = self.god.create_mock_function(
            "get_titles")
        # set up the recording
        self.loader.get_titles.expect_call().and_return(["notmylabel"])
        self.loader._run_boottool.expect_call(
            "--add-kernel \"/unittest/kernels/vmlinuz\" "
            "--title \"mylabel\" --make-default")
        # run the test
        self.loader.add_kernel("/unittest/kernels/vmlinuz",
                               "mylabel")
        self.god.check_playback()


    def test_add_kernel_adds_root(self):
        self.loader.get_titles = self.god.create_mock_function(
            "get_titles")
        # set up the recording
        self.loader.get_titles.expect_call().and_return(["notmylabel"])
        self.loader._run_boottool.expect_call(
            "--add-kernel \"/unittest/kernels/vmlinuz\" "
            "--title \"mylabel\" --root \"/unittest/root\" "
            "--make-default")
        # run the test
        self.loader.add_kernel("/unittest/kernels/vmlinuz",
                               "mylabel", root="/unittest/root")
        self.god.check_playback()


    def test_add_kernel_adds_args(self):
        self.loader.get_titles = self.god.create_mock_function(
            "get_titles")
        # set up the recording
        self.loader.get_titles.expect_call().and_return(["notmylabel"])
        self.loader._run_boottool.expect_call(
            "--add-kernel \"/unittest/kernels/vmlinuz\" "
            "--title \"mylabel\" --args \"my kernel args\" "
            "--make-default")
        # run the test
        self.loader.add_kernel("/unittest/kernels/vmlinuz",
                               "mylabel", args="my kernel args")
        self.god.check_playback()


    def test_add_kernel_adds_initrd(self):
        self.loader.get_titles = self.god.create_mock_function(
            "get_titles")
        # set up the recording
        self.loader.get_titles.expect_call().and_return(["notmylabel"])
        self.loader._run_boottool.expect_call(
            "--add-kernel \"/unittest/kernels/vmlinuz\" "
            "--title \"mylabel\" --initrd \"/unittest/initrd\" "
            "--make-default")
        # run the test
        self.loader.add_kernel("/unittest/kernels/vmlinuz",
                               "mylabel", initrd="/unittest/initrd")
        self.god.check_playback()


    def test_add_kernel_disables_make_default(self):
        self.loader.get_titles = self.god.create_mock_function(
            "get_titles")
        # set up the recording
        self.loader.get_titles.expect_call().and_return(["notmylabel"])
        self.loader._run_boottool.expect_call(
            "--add-kernel \"/unittest/kernels/vmlinuz\" "
            "--title \"mylabel\"")
        # run the test
        self.loader.add_kernel("/unittest/kernels/vmlinuz",
                               "mylabel", default=False)
        self.god.check_playback()


    def test_add_kernel_removes_old(self):
        self.loader.get_titles = self.god.create_mock_function(
            "get_titles")
        # set up the recording
        self.loader.get_titles.expect_call().and_return(["mylabel"])
        self.loader._run_boottool.expect_call(
            "--remove-kernel \"mylabel\"")
        self.loader._run_boottool.expect_call(
            "--add-kernel \"/unittest/kernels/vmlinuz\" "
            "--title \"mylabel\" --make-default")
        # run the test
        self.loader.add_kernel("/unittest/kernels/vmlinuz",
                               "mylabel")
        self.god.check_playback()


    def test_remove_kernel(self):
        # set up the recording
        self.loader._run_boottool.expect_call("--remove-kernel=14")
        # run the test
        self.loader.remove_kernel(14)
        self.god.check_playback()


    def test_boot_once(self):
        # set up the recording
        self.loader._run_boottool.expect_call(
            "--boot-once --title=autotest")
        # run the test
        self.loader.boot_once("autotest")
        self.god.check_playback()


if __name__ == "__main__":
    unittest.main()
