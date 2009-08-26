#!/usr/bin/python

import unittest
import common

from autotest_lib.client.common_lib.test_utils import mock
from autotest_lib.client.common_lib.hosts import base_classes


class test_host_class(unittest.TestCase):
    def setUp(self):
        self.god = mock.mock_god()


    def tearDown(self):
        self.god.unstub_all()


    def test_run_output_notimplemented(self):
        host = base_classes.Host()
        self.assertRaises(NotImplementedError, host.run_output, "fake command")


if __name__ == "__main__":
    unittest.main()
