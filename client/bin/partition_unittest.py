#!/usr/bin/python

"""Tests for autotest_lib.client.bin.partition."""

__author__ = 'gps@google.com (Gregory P. Smith)'

import os, sys, unittest
from cStringIO import StringIO
import common
from autotest_lib.client.common_lib.test_utils import mock
from autotest_lib.client.bin import partition


class FsOptions_common(object):
    def test_constructor(self):
        self.assertRaises(ValueError, partition.FsOptions, '', '', '', '')
        self.assertRaises(ValueError, partition.FsOptions, 'ext2', '', '', '')
        obj = partition.FsOptions('ext2', 'ext2_vanilla', '', '')
        obj = partition.FsOptions(fstype='ext2', fs_tag='ext2_vanilla')
        obj = partition.FsOptions('fs', 'shortie', 'mkfs opts', 'mount opts')
        self.assertEqual('fs', obj.fstype)
        self.assertEqual('shortie', obj.fs_tag)
        self.assertEqual('mkfs opts', obj.mkfs_flags)
        self.assertEqual('mount opts', obj.mount_options)


    def test__str__(self):
        str_obj = str(partition.FsOptions('abc', 'def', 'ghi', 'jkl'))
        self.assert_('FsOptions' in str_obj)
        self.assert_('abc' in str_obj)
        self.assert_('def' in str_obj)
        self.assert_('ghi' in str_obj)
        self.assert_('jkl' in str_obj)


# Test data used in GetPartitionTest below.

SAMPLE_SWAPS = """
Filename                                Type            Size    Used    Priority
/dev/hdc2                               partition       9863868 0       -1
"""

SAMPLE_PARTITIONS_HDC_ONLY = """
major minor  #blocks  name

   8    16  390711384 hdc
   8    18     530113 hdc2
   8    19  390178687 hdc3
"""

# yes I manually added a hda1 line to this output to test parsing when the Boot
# flag exists.
SAMPLE_FDISK = "/sbin/fdisk -l -u '/dev/hdc'"
SAMPLE_FDISK_OUTPUT = """
Disk /dev/hdc: 400.0 GB, 400088457216 bytes
255 heads, 63 sectors/track, 48641 cylinders, total 781422768 sectors
Units = sectors of 1 * 512 = 512 bytes

   Device Boot      Start         End      Blocks   Id  System
/dev/hdc2              63     1060289      530113+  82  Linux swap / Solaris
/dev/hdc3         1060290   781417664   390178687+  83  Linux
/dev/hdc4   *    faketest    FAKETEST      232323+  83  Linux
"""


class get_partition_list_common(object):
    def setUp(self):
        self.god = mock.mock_god()
        self.god.stub_function(os, 'popen')


    def tearDown(self):
        self.god.unstub_all()


    def test_is_linux_fs_type(self):
        for unused in xrange(4):
            os.popen.expect_call(SAMPLE_FDISK).and_return(
                    StringIO(SAMPLE_FDISK_OUTPUT))
        self.assertFalse(partition.is_linux_fs_type('/dev/hdc1'))
        self.assertFalse(partition.is_linux_fs_type('/dev/hdc2'))
        self.assertTrue(partition.is_linux_fs_type('/dev/hdc3'))
        self.assertTrue(partition.is_linux_fs_type('/dev/hdc4'))
        self.god.check_playback()


    def test_get_partition_list(self):
        def fake_open(filename):
            """Fake open() to pass to get_partition_list as __open."""
            if filename == '/proc/swaps':
                return StringIO(SAMPLE_SWAPS)
            elif filename == '/proc/partitions':
                return StringIO(SAMPLE_PARTITIONS_HDC_ONLY)
            else:
                self.assertFalse("Unexpected open() call: %s" % filename)

        job = 'FakeJob'

        # Test a filter func that denies all.
        parts = partition.get_partition_list(job, filter_func=lambda x: False,
                                             open_func=fake_open)
        self.assertEqual([], parts)
        self.god.check_playback()

        # Test normal operation.
        self.god.stub_function(partition, 'partition')
        partition.partition.expect_call(job, '/dev/hdc3').and_return('3')
        parts = partition.get_partition_list(job, open_func=fake_open)
        self.assertEqual(['3'], parts)
        self.god.check_playback()

        # Test exclude_swap can be disabled.
        partition.partition.expect_call(job, '/dev/hdc2').and_return('2')
        partition.partition.expect_call(job, '/dev/hdc3').and_return('3')
        parts = partition.get_partition_list(job, exclude_swap=False,
                                             open_func=fake_open)
        self.assertEqual(['2', '3'], parts)
        self.god.check_playback()

        # Test that min_blocks works.
        partition.partition.expect_call(job, '/dev/hdc3').and_return('3')
        parts = partition.get_partition_list(job, min_blocks=600000,
                                             exclude_swap=False,
                                             open_func=fake_open)
        self.assertEqual(['3'], parts)
        self.god.check_playback()


# we want to run the unit test suite once strictly on the non site specific
# version of partition (ie on base_partition.py) and once on the version
# that would result after the site specific overrides take place in order
# to check that the overrides to not break expected functionality of the
# non site specific code
class FSOptions_base_test(FsOptions_common, unittest.TestCase):
    def setUp(self):
        sys.modules['autotest_lib.client.bin.site_partition'] = None
        reload(partition)


class get_partition_list_base_test(get_partition_list_common, unittest.TestCase):
    def setUp(self):
        sys.modules['autotest_lib.client.bin.site_partition'] = None
        reload(partition)
        get_partition_list_common.setUp(self)


class FSOptions_test(FsOptions_common, unittest.TestCase):
    def setUp(self):
        if 'autotest_lib.client.bin.site_partition' in sys.modules:
            del sys.modules['autotest_lib.client.bin.site_partition']
        reload(partition)


class get_partition_list_test(get_partition_list_common, unittest.TestCase):
    def setUp(self):
        if 'autotest_lib.client.bin.site_partition' in sys.modules:
            del sys.modules['autotest_lib.client.bin.site_partition']
        reload(partition)
        get_partition_list_common.setUp(self)


if __name__ == '__main__':
    unittest.main()
