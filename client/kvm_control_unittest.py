#!/usr/bin/env python
# -*- coding: utf-8 -*-

import unittest
from StringIO import StringIO

try:
    import autotest.common as common  # pylint: disable=W0611
except ImportError:
    import common  # pylint: disable=W0611

from autotest.client import kvm_control, base_utils, utils
from autotest.client.shared.test_utils import mock
from autotest.client.shared import error


class test_kvm_control(unittest.TestCase):

    """
    Test suite for the autotest.client.kvm_control class
    """

    def setUp(self):
        self.god = mock.mock_god()

    def tearDown(self):
        self.god.unstub_all()

    def _mock_cpu_info(self, data):
        """
        Mock function for `autotest.client.utils.get_cpu_info` function
        """
        lines = StringIO(data).readlines()
        self.god.stub_with(base_utils, 'get_cpu_info',
                           lambda: lines)

    def _mock_utils_system(self, command):
        """
        Mock function for `autotest.client.shared.utils.system`
        """
        self.god.stub_with(utils, 'system', lambda c: command)

    def test_get_kvm_arch(self):
        """
        Asserts for `autotest.client.kvm_control.get_kvm_arch`

        :returns: None
        """
        self._mock_cpu_info("GenuineIntel\nvmx")
        self.assertTrue(kvm_control.get_kvm_arch() == 'kvm_intel')

        self._mock_cpu_info("AuthenticAMD\nsvm")
        self.assertTrue(kvm_control.get_kvm_arch() == 'kvm_amd')

        self._mock_cpu_info("POWER7")
        self.assertTrue(kvm_control.get_kvm_arch() == 'kvm_power7')

        self._mock_cpu_info("AuthenticAMD")
        self.assertRaises(error.TestError, kvm_control.get_kvm_arch)

        self._mock_cpu_info("InvalidCPU")
        self.assertRaises(error.TestError, kvm_control.get_kvm_arch)

    def test_load_kvm(self):
        """
        Asserts for `autotest.client.kvm_control.load_kvm`

        :returns: None
        """
        self._mock_utils_system(0)
        self._mock_cpu_info("GenuineIntel\nvmx")
        self.assertTrue(kvm_control.load_kvm() == 0)

        self._mock_utils_system(1)
        self._mock_cpu_info("GenuineIntel\nvmx")
        self.assertTrue(kvm_control.load_kvm() == 1)

        self._mock_utils_system(0)
        self._mock_cpu_info("POWER7")
        self.assertTrue(kvm_control.load_kvm() == 0)

    def test_unload_kvm(self):
        """
        Asserts for `autotest.client.kvm_control.unload_kvm`

        :returns: None
        """
        self._mock_utils_system(0)
        self._mock_cpu_info("GenuineIntel\nvmx")
        self.assertTrue(kvm_control.unload_kvm() == 0)

        self._mock_utils_system(1)
        self._mock_cpu_info("GenuineIntel\nvmx")
        self.assertTrue(kvm_control.load_kvm() == 1)

        self._mock_utils_system(0)
        self._mock_cpu_info("POWER7")
        self.assertTrue(kvm_control.load_kvm() == 0)


if __name__ == '__main__':
    unittest.main()
