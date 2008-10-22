#!/usr/bin/python

"""Tests for fsdev_disks."""

__author__ = 'gps@google.com (Gregory Smith)'

import unittest
import common
from autotest_lib.client.bin import fsdev_disks

class fsdev_disks_test(unittest.TestCase):
    def test_legacy_str_to_test_flags(self):
        obj = fsdev_disks._legacy_str_to_test_flags(
                'ext2 / -q               /                          / ext2')
        self.assertEqual('ext2', obj.filesystem)
        self.assertEqual('-q', obj.mkfs_flags)
        self.assertEqual('', obj.mount_options)
        self.assertEqual('ext2', obj.short_name)
        obj = fsdev_disks._legacy_str_to_test_flags(
                'xfs  / -f -l size=128m / logbufs=8,logbsize=32768 / xfs_log8')
        self.assertEqual('xfs', obj.filesystem)
        self.assertEqual('logbufs=8,logbsize=32768', obj.mount_options)
        self.assertEqual('xfs_log8', obj.short_name)


if __name__ == '__main__':
    unittest.main()
