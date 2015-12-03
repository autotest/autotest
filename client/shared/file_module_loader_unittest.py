#!/usr/bin/env python

#  Copyright(c) 2014 Intel Corporation.
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
import unittest
from tempfile import mkstemp

import file_module_loader


class TestFileModuleLoader(unittest.TestCase):

    @staticmethod
    def test_load_module_from_file():
        tmp_fd, tmp_path = mkstemp()
        try:
            tmpfile = os.fdopen(tmp_fd, "w")
            try:
                tmpfile.write("""
import sys
some_value = 'some_value'
print sys.dont_write_bytecode
bytecode_val = sys.dont_write_bytecode
""")
                tmpfile.flush()
                tmpfile.seek(0)
            finally:
                tmpfile.close()

            assert not sys.dont_write_bytecode
            new_module = file_module_loader.load_module_from_file(tmp_path)
            assert new_module.some_value == 'some_value'
            assert new_module.bytecode_val
            assert not sys.dont_write_bytecode
        finally:
            os.remove(tmp_path)

    class NameSpace(object):

        def __init__(self):
            self.__dict__['actions'] = []

        def __delattr__(self, item):
            self.__dict__['actions'].append(("del", item))
            del self.__dict__[item]

        def __setattr__(self, item, val):
            self.__dict__['actions'].append(("set", item, val))
            self.__dict__[item] = val

    def test_preserve_value_resets_when_exists(self):
        namespace = self.NameSpace()
        namespace.wow = "wow"
        assert namespace.wow == "wow"

        @file_module_loader.preserve_value(namespace, "wow")
        def changer():
            namespace.wow = "bar"
            assert namespace.wow == "bar"
        changer()
        assert namespace.wow == "wow"
        assert namespace.__dict__['actions'] == [
            ("set", "wow", "wow"),
            ("set", "wow", "bar"),
            ("set", "wow", "wow"),
        ]

    def test_preserve_value_deletes_when_didnt_exist(self):
        namespace = self.NameSpace()
        assert not hasattr(namespace, "wow")

        @file_module_loader.preserve_value(namespace, "wow")
        def changer():
            namespace.wow = "bar"
        changer()
        assert changer.__name__ == "changer"
        assert namespace.__dict__['actions'] == [
            ("set", "wow", "bar"),
            ("del", "wow"),
        ]
        assert not hasattr(namespace, "wow")

if __name__ == '__main__':
    unittest.main()
