#!/usr/bin/python

"""Unit Tests for autotest.client.shared.test"""

__author__ = 'gps@google.com (Gregory P. Smith)'

import unittest
try:
    import autotest.common as common  # pylint: disable=W0611
except ImportError:
    import common  # pylint: disable=W0611
from autotest.client.shared import test
from autotest.client.shared.test_utils import mock


class TestTestCase(unittest.TestCase):

    class _neutered_base_test(test.base_test):

        """A child class of base_test to avoid calling the constructor."""

        def __init__(self, *args, **kwargs):
            class MockJob(object):
                pass

            class MockProfilerManager(object):

                def active(self):
                    return False

                def present(self):
                    return True
            self.job = MockJob()
            self.job.default_profile_only = False
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
        self.test.postprocess_iteration.expect_call()
        self.test.analyze_perf_constraints.expect_call([])
        after_hook.expect_call(self.test)
        self.test._call_run_once([], False, None, (1, 2), {'arg': 'val'})
        self.god.check_playback()

    def test_call_run_once_with_exception(self):
        # setup
        self.god.stub_function(self.test, 'drop_caches_between_iterations')
        self.god.stub_function(self.test, 'run_once')
        before_hook = self.god.create_mock_function('before_hook')
        after_hook = self.god.create_mock_function('after_hook')
        self.test.register_before_iteration_hook(before_hook)
        self.test.register_after_iteration_hook(after_hook)
        error = Exception('fail')

        # tests the test._call_run_once implementation
        self.test.drop_caches_between_iterations.expect_call()
        before_hook.expect_call(self.test)
        self.test.run_once.expect_call(1, 2, arg='val').and_raises(error)
        after_hook.expect_call(self.test)
        try:
            self.test._call_run_once([], False, None, (1, 2), {'arg': 'val'})
        except Exception:
            pass
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

        fake_time = iter(range(4)).next
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
        # test that profile_only=True works.
        self.god.stub_function(self.test, 'drop_caches_between_iterations')
        self.test.drop_caches_between_iterations.expect_call()
        self.test.run_once_profiling.expect_call(None)
        self.test.drop_caches_between_iterations.expect_call()
        self.test.run_once_profiling.expect_call(None)
        self.test.postprocess.expect_call()
        self.test.process_failed_constraints.expect_call()
        self.test.execute(profile_only=True, iterations=2)
        self.god.check_playback()

    def test_execute_default_profile_only(self):
        # test that profile_only=True works.
        self.god.stub_function(self.test, 'drop_caches_between_iterations')
        for _ in range(3):
            self.test.drop_caches_between_iterations.expect_call()
            self.test.run_once_profiling.expect_call(None)
        self.test.postprocess.expect_call()
        self.test.process_failed_constraints.expect_call()
        self.test.job.default_profile_only = True
        self.test.execute(iterations=3)
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


class test_subtest(unittest.TestCase):

    """
    Test subtest class.
    """

    def setUp(self):
        self.god = mock.mock_god(ut=self)
        self.god.stub_function(test.logging, 'error')
        self.god.stub_function(test.logging, 'info')

    def tearDown(self):
        self.god.unstub_all()

    def test_test_not_implemented_raise(self):
        test.logging.info.expect_any_call()
        test.logging.error.expect_any_call()
        test.logging.error.expect_any_call()
        test.logging.error.expect_any_call()
        test.logging.info.expect_call("Subtest (test_not_implement):"
                                      " --> FAIL")

        class test_not_implement(test.Subtest):
            pass

        self.assertRaises(NotImplementedError, test_not_implement)

    def test_clean_not_implemented_raise(self):
        test.logging.info.expect_any_call()
        test.logging.info.expect_any_call()

        class test_test_not_cleanup_implement(test.Subtest):

            def test(self):
                pass

        self.assertRaises(NotImplementedError, test_test_not_cleanup_implement)

    def test_fail_in_nofatal_test(self):
        test.logging.info.expect_any_call()
        test.logging.error.expect_any_call()
        test.logging.error.expect_any_call()
        test.logging.error.expect_any_call()
        test.logging.info.expect_call("Subtest (test_raise_in_nofatal"
                                      "_test): --> FAIL")

        class test_raise_in_nofatal_test(test.Subtest):

            @test.subtest_nocleanup
            def test(self):
                raise Exception("No fatal test.")

        test_raise_in_nofatal_test()

    def test_fail_in_fatal_test(self):
        test.logging.info.expect_any_call()
        test.logging.error.expect_any_call()
        test.logging.error.expect_any_call()
        test.logging.error.expect_any_call()
        test.logging.info.expect_call("Subtest (test_raise_in_fatal"
                                      "_test): --> FAIL")

        class test_raise_in_fatal_test(test.Subtest):

            @test.subtest_nocleanup
            @test.subtest_fatal
            def test(self):
                raise Exception("Fatal test.")

        self.assertRaises(Exception, test_raise_in_fatal_test)

    def test_pass_with_cleanup_test(self):
        test.logging.info.expect_any_call()
        test.logging.info.expect_call("Subtest (test_pass_test):"
                                      " --> PASS")

        class test_pass_test(test.Subtest):

            @test.subtest_fatal
            def test(self):
                pass

            def clean(self):
                pass

        test_pass_test()

    def test_results(self):
        test.logging.info.expect_any_call()
        test.logging.info.expect_call("Subtest (test_pass_test):"
                                      " --> PASS")
        test.logging.info.expect_any_call()
        test.logging.error.expect_any_call()
        test.logging.error.expect_any_call()
        test.logging.error.expect_any_call()
        test.logging.info.expect_call("Subtest (test_raise_in_nofatal"
                                      "_test): --> FAIL")

        # Reset test fail count.
        test.Subtest.failed = 0

        class test_pass_test(test.Subtest):

            @test.subtest_fatal
            def test(self):
                pass

            def clean(self):
                pass

        class test_raise_in_nofatal_test(test.Subtest):

            @test.subtest_nocleanup
            def test(self):
                raise Exception("No fatal test.")

        test_pass_test()
        test_raise_in_nofatal_test()
        self.assertEqual(test.Subtest.has_failed(), True,
                         "Subtest class did not catch subtest failure.")
        self.assertEqual(test.Subtest.failed, 1,
                         "Subtest count failure is wrong")


if __name__ == '__main__':
    unittest.main()
