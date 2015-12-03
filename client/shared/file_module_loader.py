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


import imp
import os
import sys


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

        wrapper.__name__ = func.__name__
        wrapper.__doc__ = func.__doc__

        return wrapper

    return decorator


# WARNING: dont_write_bytecode doesn't exist in Python 2.4 so it won't do
# anything.
@preserve_value(sys, 'dont_write_bytecode')
def _load_module_no_bytecode(filename, module_file, module_file_path, py_source_description):
    """
    Helper function to load a module while setting sys.dont_write_bytecode to prevent bytecode files from being
    generator.

    For example, if the module name is 'foo', then python will write 'fooc' as the bytecode.  This is not desirable.

    WARNING: dont_write_bytecode doesn't exist in Python 2.4 so you will get bytecode files.

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
    Load module from any filename, modified from http://stackoverflow.com/a/6811925
    Do not write bytecode.

    :param module_file_path: path to file with or without .py
    :type module_file_path:  str
    :return: module
    :rtype: module
    :author: bignose  http://stackoverflow.com/users/70157/bignose
    :license: http://creativecommons.org/licenses/by-sa/3.0/
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
