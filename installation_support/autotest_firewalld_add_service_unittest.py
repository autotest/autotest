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

import imp
import os
import sys
import unittest

try:
    import autotest.common as common  # pylint: disable=W0611
except ImportError:
    import common  # pylint: disable=W0611

from autotest.client.shared.mock import patch


def preserve_value(namespace, name):
    """
    Function decorator to wrap a function that sets a namespace item.
    In particular if we modify a global namespace and want to restore the value
    after we have finished, use this function.

    This is decorator version of the context manager from
    http://stackoverflow.com/a/6811921. We use a decorator since Python 2.4
    doesn't have context managers.

    :param namespace: namespace to modify, e.g. sys
    :type namespace: object
    :param name: attribute in the namespace, e.g. dont_write_bytecode
    :type name: str
    :return: New function decorator that wraps the attribute modification
    :rtype: function
    """

    def decorator(func):

        def resetter_attr(saved_value_internal):
            return setattr(namespace, name, saved_value_internal)

        def resetter_no_attr(saved_value_internal):
            del saved_value_internal
            return delattr(namespace, name)

        def wrapper(*args, **kwargs):
            saved_value = None
            try:
                saved_value = getattr(namespace, name)
                resetter = resetter_attr
            except AttributeError:
                # the attribute didn't exist before, so delete it when we are
                # done
                resetter = resetter_no_attr
            try:
                return func(*args, **kwargs)
            finally:
                resetter(saved_value)

        return wrapper

    return decorator


# WARNING: dont_write_bytecode doesn't exist in Python 2.4 so it won't do
# anything.
@preserve_value(sys, 'dont_write_bytecode')
def _load_module_no_bytecode(filename, module_file, module_file_path,
                             py_source_description):
    """
    Helper function to load a module while setting sys.dont_write_bytecode
    to prevent bytecode files from being generated.

    For example, if the module name is 'foo', then python will write 'fooc'
    as the bytecode.  This is not desirable.

    :type filename: str
    :type module_file: open
    :type module_file_path: str
    :type py_source_description: tuple
    :return: imported module
    :rtype: module
    """
    sys.dont_write_bytecode = 1
    new_module = imp.load_module(
        os.path.splitext(filename)[0].replace("-", "_"),
        module_file, module_file_path, py_source_description)
    return new_module


def load_module_from_file(module_file_path):
    """
    Load module from any filename (mod from http://stackoverflow.com/a/6811925)

    :param module_file_path: path to file with or without .py
    :type module_file_path:  str
    :return: module
    :rtype: module
    """
    filename = os.path.basename(module_file_path)
    py_source_open_mode = "U"
    py_source_description = (".py", py_source_open_mode, imp.PY_SOURCE)
    module_file = open(module_file_path, py_source_open_mode)
    try:
        new_module = _load_module_no_bytecode(
            filename, module_file, module_file_path, py_source_description)
    finally:
        module_file.close()
    return new_module

MODULE_FILE = "autotest-firewalld-add-service"

ETC_PATH = os.path.join(os.sep, "etc", "firewalld", "zones", "public.xml")
USR_LIB_PATH = os.path.join(
    os.sep, "usr", "lib", "firewalld", "zones", "public.xml")

test_path = os.path.dirname(os.path.realpath(__file__))


# Mock out argparse
class MockArgParse(object):

    class ArgumentParser(object):

        def add_argument(self, *args, **kwargs):
            pass
sys.modules['argparse'] = MockArgParse
autotest_firewall_module = load_module_from_file(
    os.path.join(test_path, MODULE_FILE))


class TestFirewalldAddService(unittest.TestCase):

    def setUp(self):
        self.app = autotest_firewall_module.App()

    def test_etc_firewalld_exists(self):
        self.app.try_open = lambda *args: ETC_PATH
        found_path = self.app.get_src_file_from_zone("public")
        assert ETC_PATH == found_path

    def test_etc_firewalld_does_not_exists(self):
        def try_open(*args):
            if args[0] == ETC_PATH:
                return ''
            else:
                return args[0]
        self.app.try_open = try_open
        found_path = self.app.get_src_file_from_zone("public")
        assert USR_LIB_PATH == found_path

    def test_try_open(self):
        assert self.app.try_open("\x03") == ''

    def test_run_complains_about_missing_zone(self):
        @patch.object(self.app, "add_service")
        @patch.object(autotest_firewall_module, "logging")
        @patch.object(autotest_firewall_module, "ArgumentParser",
                      **{"return_value.parse_args.return_value.zone": "",
                         "return_value.parse_args.return_value.service": "http"}
                      )
        def _(*args):
            arg_mock, logging_mock, add_service_mock = args
            try:
                self.app.run()
            except SystemExit:
                assert arg_mock.return_value.parse_args().zone == ""
                assert "zone" in logging_mock.error.call_args[0][0]
                assert arg_mock.return_value.print_help.call_count == 1
        _()

    def test_run_complains_about_default_zone_missing(self):
        @patch.object(self.app, "add_service")
        @patch.object(autotest_firewall_module, "logging")
        @patch.object(autotest_firewall_module, "ArgumentParser",
                      **{"return_value.parse_args.return_value.zone": None,
                         "return_value.parse_args.return_value.service": "http"}
                      )
        def _(*args):
            arg_mock, logging_mock, add_service_mock = args
            try:
                self.app.run()
            except SystemExit:
                assert arg_mock.return_value.parse_args().zone is None
                assert "default" in logging_mock.error.call_args[0][0]
                assert arg_mock.return_value.print_help.call_count == 1
        _()

    def test_run_complains_about_missing_service(self):
        @patch.object(self.app, "add_service")
        @patch.object(autotest_firewall_module, "logging")
        @patch.object(autotest_firewall_module, "ArgumentParser",
                      **{"return_value.parse_args.return_value.zone": "public",
                         "return_value.parse_args.return_value.service": ""})
        def _(*args):
            arg_mock, logging_mock, add_service_mock = args
            try:
                self.app.run()
            except SystemExit:
                assert arg_mock.return_value.parse_args().zone == "public"
                assert "service" in logging_mock.error.call_args[0][0]
                assert arg_mock.return_value.print_help.call_count == 1
        _()


class TestFirewalldArgumentParser(unittest.TestCase):

    @staticmethod
    def test_get_default_zone():
        @patch.object(
            # communicate() returns newlines
            autotest_firewall_module, "Popen",
            **{"return_value.communicate.return_value": ("public\n", ""),
               "return_value.returncode": 0})
        def _(*args):
            assert autotest_firewall_module.ArgumentParser._get_default_zone(
            ) == "public"
        _()

    @staticmethod
    def test_get_default_zone_returns_None_when_error():
        @patch.object(
            # communicate() returns newlines
            autotest_firewall_module, "Popen",
            **{"return_value.communicate.return_value": ("error\n", ""),
               "return_value.returncode": 1})
        def _(*args):
            assert autotest_firewall_module.ArgumentParser._get_default_zone(
            ) is None
        _()


if __name__ == '__main__':
    unittest.main()
