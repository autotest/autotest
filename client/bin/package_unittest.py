#!/usr/bin/python


import unittest, os
import common
from autotest_lib.client.common_lib.test_utils import mock
from autotest_lib.client.bin import package, os_dep, utils


class TestPackage(unittest.TestCase):
    def setUp(self):
        self.god = mock.mock_god()
        self.god.stub_function(os_dep, "command")

    def tearDown(self):
        self.god.unstub_all()


    def info_common_setup(self, input_package, result):
        self.god.stub_function(os.path, "isfile")
        self.god.stub_function(utils, "system_output")
        self.god.stub_function(utils, "system")

        # record
        os.path.isfile.expect_call(input_package).and_return(True)
        utils.system_output.expect_call(
            'file ' + input_package).and_return(result)
        utils.system_output.expect_call(
            'file ' + input_package).and_return(result)


    def test_info_rpm(self):
        # setup
        input_package = "package.rpm"
        file_result = "rpm"
        ver = '1.0'

        # common setup
        self.info_common_setup(input_package, file_result)

        # record
        package_info = {}
        package_info['type'] = 'rpm'
        os_dep.command.expect_call('rpm')
        s_cmd = 'rpm -qp --qf %{SOURCE} ' + input_package + ' 2>/dev/null'
        a_cmd = 'rpm -qp --qf %{ARCH} ' + input_package + ' 2>/dev/null'
        v_cmd = 'rpm -qp ' + input_package + ' 2>/dev/null'

        utils.system_output.expect_call(v_cmd).and_return(ver)
        i_cmd = 'rpm -q ' + ver + ' 2>&1 >/dev/null'

        package_info['system_support'] = True
        utils.system_output.expect_call(s_cmd).and_return('source')
        package_info['source'] = True
        utils.system_output.expect_call(v_cmd).and_return(ver)
        package_info['version'] = ver
        utils.system_output.expect_call(a_cmd).and_return('586')
        package_info['arch'] = '586'
        utils.system.expect_call(i_cmd)
        package_info['installed'] = True

        # run and check
        info = package.info(input_package)
        self.god.check_playback()
        self.assertEquals(info, package_info)


    def test_info_dpkg(self):
        # setup
        input_package = "package.deb"
        file_result = "debian"
        ver = '1.0'

        # common setup
        self.info_common_setup(input_package, file_result)

        # record
        package_info = {}
        package_info['type'] = 'dpkg'
        package_info['source'] = False
        os_dep.command.expect_call('dpkg')
        a_cmd = 'dpkg -f ' + input_package + ' Architecture 2>/dev/null'
        v_cmd = 'dpkg -f ' + input_package + ' Package 2>/dev/null'
        utils.system_output.expect_call(v_cmd).and_return(ver)
        i_cmd = 'dpkg -s ' + ver + ' 2>/dev/null'
        package_info['system_support'] = True
        utils.system_output.expect_call(v_cmd).and_return(ver)
        package_info['version'] = ver
        utils.system_output.expect_call(a_cmd).and_return('586')
        package_info['arch'] = '586'
        utils.system_output.expect_call(i_cmd,
            ignore_status=True).and_return('installed')
        package_info['installed'] = True

        # run and check
        info = package.info(input_package)
        self.god.check_playback()
        self.assertEquals(info, package_info)


    def test_install(self):
        # setup
        input_package = "package.rpm"
        self.god.stub_function(package, "info")
        self.god.stub_function(utils, "system")

        # record
        package_info = {}
        package_info['type'] = 'rpm'
        package_info['system_support'] = True
        package_info['source'] = True
        package_info['installed'] = True

        package.info.expect_call(input_package).and_return(package_info)
        install_command = 'rpm %s -U %s' % ('', input_package)
        utils.system.expect_call(install_command)

        # run and test
        package.install(input_package)
        self.god.check_playback()


    def test_convert(self):
        os_dep.command.expect_call('alien')
        dest_format = 'dpkg'
        input_package = "package.rpm"
        output = "package_output.deb"

        # record
        self.god.stub_function(utils, "system_output")
        utils.system_output.expect_call(
            'alien --to-deb %s 2>/dev/null' % input_package).and_return(output)

        # run test
        package.convert(input_package, dest_format)
        self.god.check_playback()


    def test_os_support_full(self):
        # recording
        exp_support = {}
        for package_manager in package.KNOWN_PACKAGE_MANAGERS:
            os_dep.command.expect_call(package_manager)
            exp_support[package_manager] = True

        os_dep.command.expect_call('alien')
        exp_support['conversion'] = True

        # run and test
        support = package.os_support()
        self.god.check_playback()
        self.assertEquals(support, exp_support)


    def test_os_support_none(self):
        # recording
        exp_support = {}
        for package_manager in package.KNOWN_PACKAGE_MANAGERS:
            os_dep.command.expect_call(package_manager).and_raises(ValueError)
            exp_support[package_manager] = False

        os_dep.command.expect_call('alien').and_raises(ValueError)
        exp_support['conversion'] = False

        # run and test
        support = package.os_support()
        self.god.check_playback()
        self.assertEquals(support, exp_support)


if __name__ == "__main__":
    unittest.main()
