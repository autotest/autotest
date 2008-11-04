#!/usr/bin/python

"""Tests for autotest_lib.client.bin.partition."""

__author__ = 'gps@google.com (Gregory P. Smith)'

import unittest
import common
from autotest_lib.client.bin import partition


class FsOptions_test(unittest.TestCase):
    def test_constructor(self):
        self.assertRaises(ValueError, partition.FsOptions, '', '', '', '')
        self.assertRaises(ValueError, partition.FsOptions, 'ext2', '', '', '')
        obj = partition.FsOptions('ext2', '', '', 'ext2_vanilla')
        obj = partition.FsOptions('fs', 'mkfs opts', 'mount opts', 'shortie')
        self.assertEqual('fs', obj.fstype)
        self.assertEqual('mkfs opts', obj.mkfs_flags)
        self.assertEqual('mount opts', obj.mount_options)
        self.assertEqual('shortie', obj.fs_tag)


    def test__str__(self):
        str_obj = str(partition.FsOptions('abc', 'def', 'ghi', 'jkl'))
        self.assert_('FsOptions' in str_obj)
        self.assert_('abc' in str_obj)
        self.assert_('def' in str_obj)
        self.assert_('ghi' in str_obj)
        self.assert_('jkl' in str_obj)


if __name__ == '__main__':
    unittest.main()
