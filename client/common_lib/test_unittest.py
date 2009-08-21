#!/usr/bin/python

"""Unit Tests for autotest.client.common_lib.test"""

__author__ = 'gps@google.com (Gregory P. Smith)'

import unittest
from cStringIO import StringIO
import common
from autotest_lib.client.common_lib import error, test
from autotest_lib.client.common_lib.test_utils import mock

class TestTestCase(unittest.TestCase):
    class _neutered_base_test(test.base_test):
        """A child class of base_test to avoid calling the constructor."""
        def __init__(self, *args, **kwargs):
            class MockJob(object):
                pass
            class MockProfilerManager(object):
                def active(self):
                    return False
            self.job = MockJob()
            self.job.profilers = MockProfilerManager()
            self._new_keyval = False
            self.iteration = 0
            self.before_iteration_hooks = []
            self.after_iteration_hooks = []


    def setUp(self):
        self.god = mock.mock_god()
        self.test = self._neutered_base_test()


    def tearDown(self):
        self.god.unstub_all()



class Test_base_test_execute(TestTestCase):
    # Test the various behaviors of the base_test.execute() method.
    def setUp(self):
        TestTestCase.setUp(self)
        self.god.stub_function(self.test, 'run_once_profiling')
        self.god.stub_function(self.test, 'postprocess')
        self.god.stub_function(self.test, 'process_failed_constraints')


    def test_call_run_once(self):
        # setup
        self.god.stub_function(self.test, 'drop_caches_between_iterations')
        self.god.stub_function(self.test, 'run_once')
        self.god.stub_function(self.test, 'postprocess_iteration')
        self.god.stub_function(self.test, 'analyze_perf_constraints')
        before_hook = self.god.create_mock_function('before_hook')
        after_hook = self.god.create_mock_function('after_hook')
        self.test.register_before_iteration_hook(before_hook)
        self.test.register_after_iteration_hook(after_hook)

        # tests the test._call_run_once implementation
        self.test.drop_caches_between_iterations.expect_call()
        before_hook.expect_call(self.test)
        self.test.run_once.expect_call(1, 2, arg='val')
        after_hook.expect_call(self.test)
        self.test.postprocess_iteration.expect_call()
        self.test.analyze_perf_constraints.expect_call([])
        self.test._call_run_once([], False, None, (1, 2), {'arg': 'val'})
        self.god.check_playback()


    def _expect_call_run_once(self):
        self.test._call_run_once.expect_call((), False, None, (), {})


    def test_execute_test_length(self):
        # test that test_length overrides iterations and works.
        self.god.stub_function(self.test, '_call_run_once')

        self._expect_call_run_once()
        self._expect_call_run_once()
        self._expect_call_run_once()
        self.test.run_once_profiling.expect_call(None)
        self.test.postprocess.expect_call()
        self.test.process_failed_constraints.expect_call()

        fake_time = iter(xrange(4)).next
        self.test.execute(iterations=1, test_length=3, _get_time=fake_time)
        self.god.check_playback()


    def test_execute_iterations(self):
        # test that iterations works.
        self.god.stub_function(self.test, '_call_run_once')

        iterations = 2
        for _ in range(iterations):
            self._expect_call_run_once()
        self.test.run_once_profiling.expect_call(None)
        self.test.postprocess.expect_call()
        self.test.process_failed_constraints.expect_call()

        self.test.execute(iterations=iterations)
        self.god.check_playback()


    def _mock_calls_for_execute_no_iterations(self):
        self.test.run_once_profiling.expect_call(None)
        self.test.postprocess.expect_call()
        self.test.process_failed_constraints.expect_call()


    def test_execute_iteration_zero(self):
        # test that iterations=0 works.
        self._mock_calls_for_execute_no_iterations()

        self.test.execute(iterations=0)
        self.god.check_playback()


    def test_execute_profile_only(self):
        # test that profile_only=True works.  (same as iterations=0)
        self.god.stub_function(self.test, 'drop_caches_between_iterations')
        self.test.drop_caches_between_iterations.expect_call()
        self.test.run_once_profiling.expect_call(None)
        self.test.drop_caches_between_iterations.expect_call()
        self.test.run_once_profiling.expect_call(None)
        self.test.postprocess.expect_call()
        self.test.process_failed_constraints.expect_call()
        self.test.execute(profile_only=True, iterations=2)
        self.god.check_playback()


    def test_execute_postprocess_profiled_false(self):
        # test that postprocess_profiled_run=False works
        self.god.stub_function(self.test, '_call_run_once')

        self.test._call_run_once.expect_call((), False, False, (), {})
        self.test.run_once_profiling.expect_call(False)
        self.test.postprocess.expect_call()
        self.test.process_failed_constraints.expect_call()

        self.test.execute(postprocess_profiled_run=False, iterations=1)
        self.god.check_playback()


    def test_execute_postprocess_profiled_true(self):
        # test that postprocess_profiled_run=True works
        self.god.stub_function(self.test, '_call_run_once')

        self.test._call_run_once.expect_call((), False, True, (), {})
        self.test.run_once_profiling.expect_call(True)
        self.test.postprocess.expect_call()
        self.test.process_failed_constraints.expect_call()

        self.test.execute(postprocess_profiled_run=True, iterations=1)
        self.god.check_playback()


if __name__ == '__main__':
    unittest.main()
