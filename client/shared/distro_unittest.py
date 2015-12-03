#!/usr/bin/python

import os
import re
import unittest
try:
    import autotest.common as common  # pylint: disable=W0611
except ImportError:
    import common  # pylint: disable=W0611

from autotest.client.shared import distro
from autotest.client.shared.test_utils import mock


class Probe(unittest.TestCase):

    def setUp(self):
        self.god = mock.mock_god()

    def tearDown(self):
        self.god.unstub_all()

    def test_check_name_for_file_fail(self):
        class MyProbe(distro.Probe):
            CHECK_FILE = '/etc/issue'

        my_probe = MyProbe()
        self.assertFalse(my_probe.check_name_for_file())

    def test_check_name_for_file(self):
        class MyProbe(distro.Probe):
            CHECK_FILE = '/etc/issue'
            CHECK_FILE_DISTRO_NAME = 'superdistro'

        my_probe = MyProbe()
        self.assertTrue(my_probe.check_name_for_file())

    def test_check_name_for_file_contains_fail(self):
        class MyProbe(distro.Probe):
            CHECK_FILE = '/etc/issue'
            CHECK_FILE_CONTAINS = 'text'

        my_probe = MyProbe()
        self.assertFalse(my_probe.check_name_for_file_contains())

    def test_check_name_for_file_contains(self):
        class MyProbe(distro.Probe):
            CHECK_FILE = '/etc/issue'
            CHECK_FILE_CONTAINS = 'text'
            CHECK_FILE_DISTRO_NAME = 'superdistro'

        my_probe = MyProbe()
        self.assertTrue(my_probe.check_name_for_file_contains())

    def test_check_version_fail(self):
        class MyProbe(distro.Probe):
            CHECK_VERSION_REGEX = re.compile(r'distro version (\d+)')

        my_probe = MyProbe()
        self.assertFalse(my_probe.check_version())

    def test_version_returnable(self):
        class MyProbe(distro.Probe):
            CHECK_FILE = '/etc/distro-release'
            CHECK_VERSION_REGEX = re.compile(r'distro version (\d+)')

        my_probe = MyProbe()
        self.assertTrue(my_probe.check_version())

    def test_name_for_file(self):
        distro_file = '/etc/issue'
        distro_name = 'superdistro'

        self.god.stub_function(os.path, 'exists')
        os.path.exists.expect_call(distro_file).and_return(True)

        class MyProbe(distro.Probe):
            CHECK_FILE = distro_file
            CHECK_FILE_DISTRO_NAME = distro_name

        my_probe = MyProbe()
        probed_distro_name = my_probe.name_for_file()

        self.god.check_playback()
        self.assertEqual(distro_name, probed_distro_name)


if __name__ == '__main__':
    unittest.main()
