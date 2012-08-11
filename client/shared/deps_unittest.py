#!/usr/bin/env python

import os
import unittest

try:
    import autotest.common as common
except ImportError:
    import common

from autotest.client.shared import deps


class ExecutableUnittest(unittest.TestCase):


    # Just a path that is considered absolute, doesn't have to exist
    ABSOLUTE_PATH = '/abs/olute/path'

    # AFAIK there's no way an executable can be named a whitespace
    NON_EXISTING = ' '


    def test_get_executable_path_abs(self):
        '''
        get_executable_path() should return the same path given if it's
        and absolute path.
        '''
        self.assertEquals(self.ABSOLUTE_PATH,
                          deps.get_executable_path(self.ABSOLUTE_PATH))


    def test_get_executable_path_non_existing(self):
        '''
        Test behavior if the executable does not exist
        '''
        self.assertEquals(None,
                          deps.get_executable_path(self.NON_EXISTING))


    def test_executable_can_execute(self):
        '''
        Tests that we can not execute an executable that does not exist
        '''
        self.assertFalse(deps.can_execute(self.NON_EXISTING))


class PackageUnittest(unittest.TestCase):


    ABSURDLY_NAMED_PACKAGE = 'zTNxDLMiiloAKalZzaCbBMqJaaiJqMWBPIREQENG'


    def test_package_absurdly_named(self):
        self.assertRaises(deps.DependencyNotSatisfied,
                          deps.package,
                          self.ABSURDLY_NAMED_PACKAGE)


if __name__ == '__main__':
    unittest.main()
