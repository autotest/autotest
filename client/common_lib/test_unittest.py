#!/usr/bin/python2.4

"""Unit Tests for autotest.client.common_lib.test"""

__author__ = 'gps@google.com (Gregory P. Smith)'

import unittest
from cStringIO import StringIO
import common
from autotest_lib.client.common_lib import error, test, debug
from autotest_lib.client.common_lib.test_utils import mock

class TestTestCase(unittest.TestCase):
    class _neutered_base_test(test.base_test):
        """A child class of base_test to avoid calling the constructor."""
        def __init__(self, *args, **kwargs):
            self.test_log = debug.get_logger(module='tests')

            class MockJob(object):
                pass
            class MockProfilerManager(object):
                def active(self):
                    return False
            self.job = MockJob()
            self.job.profilers = MockProfilerManager()


    def setUp(self):
        self.god = mock.mock_god()
        self.test = self._neutered_base_test()


    def tearDown(self):
        self.god.unstub_all()



class Test_base_test(TestTestCase):
    def setUp(self):
        TestTestCase.setUp(self)
        self.god.stub_function(self.test, 'cleanup')
        self.god.stub_function(test, '_cherry_pick_args')


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


class Test_base_test_execute(TestTestCase):
    # Test the various behaviors of the base_test.execute() method.
    def setUp(self):
        TestTestCase.setUp(self)
        self.god.stub_function(self.test, 'warmup')
        self.god.stub_function(self.test, 'drop_caches_between_iterations')
        self.god.stub_function(self.test, 'run_once')
        self.god.stub_function(self.test, 'postprocess_iteration')
        self.god.stub_function(self.test, 'run_once_profiling')
        self.god.stub_function(self.test, 'postprocess')

        self.test.warmup.expect_call()


    def test_execute_test_length(self):
        # test that test_length overrides iterations and works.
        self.test.drop_caches_between_iterations.expect_call()
        self.test.run_once.expect_call()
        self.test.postprocess_iteration.expect_call()
        self.test.drop_caches_between_iterations.expect_call()
        self.test.run_once.expect_call()
        self.test.postprocess_iteration.expect_call()
        self.test.drop_caches_between_iterations.expect_call()
        self.test.run_once.expect_call()
        self.test.postprocess_iteration.expect_call()
        self.test.run_once_profiling.expect_call(None)
        self.test.postprocess.expect_call()

        fake_time = iter(xrange(4)).next
        self.test.execute(iterations=1, test_length=3, _get_time=fake_time)
        self.god.check_playback()


    def test_execute_iterations(self):
        # test that iterations works.
        iterations = 2
        for _ in range(iterations):
            self.test.drop_caches_between_iterations.expect_call()
            self.test.run_once.expect_call()
            self.test.postprocess_iteration.expect_call()
        self.test.run_once_profiling.expect_call(None)
        self.test.postprocess.expect_call()

        self.test.execute(iterations=iterations)
        self.god.check_playback()


    def _mock_calls_for_execute_no_iterations(self):
        self.test.run_once_profiling.expect_call(None)
        self.test.postprocess.expect_call()


    def test_execute_iteration_zero(self):
        # test that iterations=0 works.
        self._mock_calls_for_execute_no_iterations()

        self.test.execute(iterations=0)
        self.god.check_playback()


    def test_execute_profile_only(self):
        # test that profile_only=True works.  (same as iterations=0)
        self._mock_calls_for_execute_no_iterations()

        self.test.execute(profile_only=True, iterations=2)
        self.god.check_playback()


    def test_execute_postprocess_profiled_false(self):
        # test that postprocess_profiled_run=False works
        self.test.drop_caches_between_iterations.expect_call()
        self.test.run_once.expect_call()
        self.test.postprocess_iteration.expect_call()
        self.test.run_once_profiling.expect_call(False)
        self.test.postprocess.expect_call()

        self.test.execute(postprocess_profiled_run=False, iterations=1)
        self.god.check_playback()


    def test_execute_postprocess_profiled_true(self):
        # test that postprocess_profiled_run=True works
        self.test.drop_caches_between_iterations.expect_call()
        self.test.run_once.expect_call()
        self.test.postprocess_iteration.expect_call()
        self.test.run_once_profiling.expect_call(True)
        self.test.postprocess.expect_call()

        self.test.execute(postprocess_profiled_run=True, iterations=1)
        self.god.check_playback()


if __name__ == '__main__':
    unittest.main()
