#!/usr/bin/python2.4

"""Unit Tests for autotest.client.common_lib.test"""

__author__ = 'gps@google.com (Gregory P. Smith)'

import unittest
from cStringIO import StringIO
import common
from autotest_lib.client.common_lib import error, test
from autotest_lib.client.common_lib.test_utils import mock


class Test_base_test(unittest.TestCase):
    class _neutered_base_test(test.base_test):
        """A child class of base_test to avoid calling the constructor."""
        def __init__(self, *args, **kwargs):
            pass


    def setUp(self):
        self.god = mock.mock_god()
        self.test = self._neutered_base_test()
        cleanup = self.god.stub_function(self.test, 'cleanup')
        self.god.stub_function(test, '_cherry_pick_args')


    def tearDown(self):
        self.god.unstub_all()


    def test_run_cleanup_normal(self):
        # Normal, good, no errors test.
        test._cherry_pick_args.expect_call(self.test.cleanup,
                                           (), {}).and_return(((), {}))
        self.test.cleanup.expect_call()
        self.test._run_cleanup((), {})
        self.god.check_playback()


    def test_run_cleanup_autotest_error_passthru(self):
        # Cleanup func raises an error.AutotestError, it should pass through.
        test._cherry_pick_args.expect_call(self.test.cleanup,
                                           (), {}).and_return(((), {}))
        self.test.cleanup.expect_call().and_raises(error.TestFail)
        self.assertRaises(error.TestFail, self.test._run_cleanup, (), {})
        self.god.check_playback()


    def test_run_cleanup_other_error(self):
        # Cleanup func raises a RuntimeError, it should turn into an ERROR.
        test._cherry_pick_args.expect_call(self.test.cleanup,
                                           (), {}).and_return(((), {}))
        self.test.cleanup.expect_call().and_raises(RuntimeError)
        self.assertRaises(error.TestError, self.test._run_cleanup, (), {})
        self.god.check_playback()


if __name__ == '__main__':
    unittest.main()
