#!/usr/bin/python
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

import os
import sys
import imp
import unittest


def load_module_from_file(module_file_path):
    """
    Load module from any filename, modified from by http://stackoverflow.com/a/6811925
    :param module_file_path: path to file with or without .py
    :type module_file_path:  str
    :return: module
    :rtype: module
    """
    filename = os.path.basename(module_file_path)
    sys.dont_write_bytecode = 1
    py_source_open_mode = "U"
    py_source_description = (".py", py_source_open_mode, imp.PY_SOURCE)
    module_file = open(module_file_path, py_source_open_mode)
    try:
        new_module = imp.load_module(
            os.path.splitext(filename)[0].replace("-", "_"),
            module_file, module_file_path, py_source_description)
    finally:
        module_file.close()
    return new_module

MODULE_FILE = "autotest-firewalld-add-service"

ETC_PATH = "/etc/firewalld/zones/public.xml"
USR_LIB_PATH = "/usr/lib/firewalld/zones/public.xml"


class TestFirewalldAddService(unittest.TestCase):

    def setUp(self):
        test_path = os.path.dirname(os.path.realpath(__file__))
        self.autotestd_module = load_module_from_file(
            os.path.join(test_path, MODULE_FILE))
        self.app = self.autotestd_module.App()

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

if __name__ == '__main__':
    unittest.main()
