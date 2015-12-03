#!/usr/bin/env python
#
#  Copyright(c) 2013 Intel Corporation.
#
#  This program is free software; you can redistribute it and/or modify it
#  under the terms and conditions of the GNU General Public License,
#  version 2, as published by the Free Software Foundation.
#
#  This program is distributed in the hope it will be useful, but WITHOUT
#  ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or
#  FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public License for
#  more details.
#
#  You should have received a copy of the GNU General Public License along with
#  this program; if not, write to the Free Software Foundation, Inc.,
#  51 Franklin St - Fifth Floor, Boston, MA 02110-1301 USA.
#
#  The full GNU General Public License is included in this distribution in
#  the file called "COPYING".

import unittest

try:
    import autotest.common as common  # pylint: disable=W0611
except ImportError:
    import common  # pylint: disable=W0611

from autotest.client.shared import service

from mock import MagicMock, patch


class TestSystemd(unittest.TestCase):

    def setUp(self):
        self.service_name = "fake_service"
        init_name = "systemd"
        command_generator = service._command_generators[init_name]
        self.service_command_generator = service._ServiceCommandGenerator(
            command_generator)

    def test_all_commands(self):
        for cmd in (c for c in self.service_command_generator.commands if c not in ["list", "set_target"]):
            ret = getattr(
                self.service_command_generator, cmd)(self.service_name)
            if cmd == "is_enabled":
                cmd = "is-enabled"
            assert ret == ["systemctl", cmd, "%s.service" % self.service_name]

    def test_set_target(self):
        ret = getattr(
            self.service_command_generator, "set_target")("multi-user.target")
        assert ret == ["systemctl", "isolate", "multi-user.target"]


class TestSysVInit(unittest.TestCase):

    def setUp(self):
        self.service_name = "fake_service"
        init_name = "init"
        command_generator = service._command_generators[init_name]
        self.service_command_generator = service._ServiceCommandGenerator(
            command_generator)

    def test_all_commands(self):
        command_name = "service"
        for cmd in (c for c in self.service_command_generator.commands if c not in ["list", "set_target"]):
            ret = getattr(
                self.service_command_generator, cmd)(self.service_name)
            if cmd == "is_enabled":
                command_name = "chkconfig"
                cmd = ""
            elif cmd == 'enable':
                command_name = "chkconfig"
                cmd = "on"
            elif cmd == 'disable':
                command_name = "chkconfig"
                cmd = "off"
            assert ret == [command_name, self.service_name, cmd]

    def test_set_target(self):
        ret = getattr(
            self.service_command_generator, "set_target")("multi-user.target")
        assert ret == ["telinit", "3"]


class TestSpecificServiceManager(unittest.TestCase):

    def setUp(self):
        self.run_mock = MagicMock()
        self.init_name = "init"
        get_name_of_init_mock = MagicMock(return_value="init")

        @patch.object(service, "get_name_of_init", get_name_of_init_mock)
        def patch_service_command_generator():
            return service._auto_create_specific_service_command_generator()

        @patch.object(service, "get_name_of_init", get_name_of_init_mock)
        def patch_service_result_parser():
            return service._auto_create_specific_service_result_parser()
        service_command_generator = patch_service_command_generator()
        service_result_parser = patch_service_result_parser()
        self.service_manager = service._SpecificServiceManager(
            "boot.lldpad", service_command_generator,
            service_result_parser, self.run_mock)

    def test_start(self):
        service = "lldpad"
        self.service_manager.start()
        assert self.run_mock.call_args[0][
            0] == "service boot.%s start" % service

    def test_stop_with_args(self):
        service = "lldpad"
        self.service_manager.stop(ignore_status=True)
        assert self.run_mock.call_args[0][
            0] == "service boot.%s stop" % service

    def test_list_is_not_present_in_SpecifcServiceManager(self):
        assert not hasattr(self.service_manager, "list")

    def test_set_target_is_not_present_in_SpecifcServiceManager(self):
        assert not hasattr(self.service_manager, "set_target")


class TestServiceManager(unittest.TestCase):

    @staticmethod
    def get_service_manager_from_init_and_run(init_name, run_mock):
        command_generator = service._command_generators[init_name]
        result_parser = service._result_parsers[init_name]
        service_manager = service._service_managers[init_name]
        service_command_generator = service._ServiceCommandGenerator(
            command_generator)
        service_result_parser = service._ServiceResultParser(result_parser)
        return service_manager(service_command_generator, service_result_parser, run_mock)


class TestSystemdServiceManager(TestServiceManager):

    def setUp(self):
        self.run_mock = MagicMock()
        self.init_name = "systemd"
        self.service_manager = super(TestSystemdServiceManager,
                                     self).get_service_manager_from_init_and_run(self.init_name,
                                                                                 self.run_mock)

    def test_start(self):
        service = "lldpad"
        self.service_manager.start(service)
        assert self.run_mock.call_args[0][
            0] == "systemctl start %s.service" % service

    def test_list(self):
        list_result_mock = MagicMock(exit_status=0, stdout="sshd.service enabled\n"
                                                           "vsftpd.service disabled\n"
                                                           "systemd-sysctl.service static\n")
        run_mock = MagicMock(return_value=list_result_mock)
        service_manager = super(TestSystemdServiceManager,
                                self).get_service_manager_from_init_and_run(self.init_name,
                                                                            run_mock)
        list_result = service_manager.list(ignore_status=False)
        assert run_mock.call_args[0][
            0] == "systemctl list-unit-files --type=service --no-pager --full"
        assert list_result == {'sshd': "enabled",
                               'vsftpd': "disabled",
                               'systemd-sysctl': "static"}

    def test_set_default_runlevel(self):
        runlevel = service.convert_sysv_runlevel(3)
        mktemp_mock = MagicMock(return_value="temp_filename")
        symlink_mock = MagicMock()
        rename_mock = MagicMock()

        @patch.object(service, "mktemp", mktemp_mock)
        @patch("os.symlink", symlink_mock)
        @patch("os.rename", rename_mock)
        def _():
            self.service_manager.change_default_runlevel(runlevel)
            assert mktemp_mock.called
            assert symlink_mock.call_args[0][
                0] == "/usr/lib/systemd/system/multi-user.target"
            assert rename_mock.call_args[0][
                1] == "/etc/systemd/system/default.target"
        _()

    def test_unknown_runlevel(self):
        self.assertRaises(ValueError,
                          service.convert_systemd_target_to_runlevel, "unknown")

    def test_runlevels(self):
        assert service.convert_sysv_runlevel(0) == "poweroff.target"
        assert service.convert_sysv_runlevel(1) == "rescue.target"
        assert service.convert_sysv_runlevel(2) == "multi-user.target"
        assert service.convert_sysv_runlevel(5) == "graphical.target"
        assert service.convert_sysv_runlevel(6) == "reboot.target"


class TestSysVInitServiceManager(TestServiceManager):

    def setUp(self):
        self.run_mock = MagicMock()
        self.init_name = "init"
        self.service_manager = super(TestSysVInitServiceManager,
                                     self).get_service_manager_from_init_and_run(self.init_name,
                                                                                 self.run_mock)

    def test_list(self):
        list_result_mock = MagicMock(exit_status=0,
                                     stdout="sshd             0:off   1:off   2:off   3:off   4:off   5:off   6:off\n"
                                            "vsftpd           0:off   1:off   2:off   3:off   4:off   5:on   6:off\n"
                                            "xinetd based services:\n"
                                            "        amanda:         off\n"
                                            "        chargen-dgram:  on\n")

        run_mock = MagicMock(return_value=list_result_mock)
        service_manager = super(TestSysVInitServiceManager,
                                self).get_service_manager_from_init_and_run(self.init_name,
                                                                            run_mock)
        list_result = service_manager.list(ignore_status=False)
        assert run_mock.call_args[0][
            0] == "chkconfig --list"
        assert list_result == {'sshd': {0: "off", 1: "off", 2: "off", 3: "off", 4: "off", 5: "off", 6: "off"},
                               'vsftpd': {0: "off", 1: "off", 2: "off", 3: "off", 4: "off", 5: "on", 6: "off"},
                               'xinetd': {'amanda': "off", 'chargen-dgram': "on"}}

    def test_enable(self):
        service = "lldpad"
        self.service_manager.enable(service)
        assert self.run_mock.call_args[0][0] == "chkconfig lldpad on"

    def test_unknown_runlevel(self):
        self.assertRaises(ValueError,
                          service.convert_sysv_runlevel, "unknown")

    def test_runlevels(self):
        assert service.convert_systemd_target_to_runlevel(
            "poweroff.target") == '0'
        assert service.convert_systemd_target_to_runlevel(
            "rescue.target") == 's'
        assert service.convert_systemd_target_to_runlevel(
            "multi-user.target") == '3'
        assert service.convert_systemd_target_to_runlevel(
            "graphical.target") == '5'
        assert service.convert_systemd_target_to_runlevel(
            "reboot.target") == '6'


if __name__ == '__main__':
    unittest.main()
