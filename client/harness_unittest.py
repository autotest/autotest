#!/usr/bin/python
import unittest
try:
    import autotest.common as common
except ImportError:
    import common
from autotest.client.shared.test_utils import mock
from autotest.client import harness, harness_standalone


class harness_unittest(unittest.TestCase):

    def setUp(self):
        self.god = mock.mock_god()

    def tearDown(self):
        self.god.unstub_all()

    def test_select_none(self):
        job = object()
        self.god.stub_class(harness_standalone, "harness_standalone")

        harness_args = ''
        harness_standalone.harness_standalone.expect_new(job, harness_args)
        harness.select(None, job, harness_args)
        self.god.check_playback()

    def test_select_standalone(self):
        job = object()
        self.god.stub_class(harness_standalone, "harness_standalone")

        harness_args = ''
        harness_standalone.harness_standalone.expect_new(job, harness_args)
        harness.select('standalone', job, harness_args)
        self.god.check_playback()


if __name__ == "__main__":
    unittest.main()
