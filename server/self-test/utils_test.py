#!/usr/bin/python
#
# Copyright 2007 Google Inc. Released under the GPL v2

"""This module defines the unittests for the utils
"""

__author__ = """stutsman@google.com (Ryan Stutsman)"""

import os
import sys
import os.path
import unittest

import common

from autotest_lib.server import utils


class UtilsTestCase(unittest.TestCase):
    def setUp(self):
        pass


    def tearDown(self):
        pass


    def testGetWithOpenFile(self):
        tmpdir = utils.get_tmp_dir()
        tmppath = os.path.join(tmpdir, 'testfile')
        tmpfile = file(tmppath, 'w')
        print >> tmpfile, 'Test string'
        tmpfile.close()
        tmpfile = file(tmppath)
        newtmppath = utils.get(tmpfile)
        self.assertEqual(file(newtmppath).read(), 'Test string\n')


    def testGetWithHTTP(self):
        # Yeah, this test is a bad idea, oh well
        url = 'http://www.kernel.org/pub/linux/kernel/README'
        tmppath = utils.get(url)
        f = file(tmppath)
        f.readline()
        self.assertTrue('Linux' in f.readline().split())


    def testGetWithPath(self):
        path = utils.get('/proc/cpuinfo')
        self.assertTrue(file(path).readline().startswith('processor'))


    def testGetWithString(self):
        path = utils.get('/tmp loves rabbits!')
        self.assertTrue(file(path).readline().startswith('/tmp loves'))


    def testGetWithDir(self):
        tmpdir = utils.get_tmp_dir()
        origpath = os.path.join(tmpdir, 'testGetWithDir')
        os.mkdir(origpath)
        dstpath = utils.get(origpath)
        self.assertTrue(dstpath.endswith('/'))
        self.assertTrue(os.path.isdir(dstpath))


def suite():
    return unittest.TestLoader().loadTestsFromTestCase(UtilsTestCase)

if __name__ == '__main__':
    unittest.TextTestRunner(verbosity=2).run(suite())
