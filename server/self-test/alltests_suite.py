#!/usr/bin/python
#
# Copyright 2007 Google Inc. Released under the GPL v2

"""This module provides a means to run all the unittests for autoserv
"""

__author__ = """stutsman@google.com (Ryan Stutsman)"""

import os, sys

# Adjust the path so Python can find the autoserv modules
src = os.path.abspath("%s/.." % (os.path.dirname(sys.argv[0]),))
if src not in sys.path:
    sys.path.insert(1, src)

import unittest


import autotest_test
import utils_test


def suite():
    return unittest.TestSuite([autotest_test.suite(),
                               utils_test.suite()])


if __name__ == '__main__':
    unittest.TextTestRunner(verbosity=2).run(suite())
