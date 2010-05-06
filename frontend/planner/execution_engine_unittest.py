#!/usr/bin/python

import unittest
import common
from autotest_lib.frontend import setup_django_environment
from autotest_lib.client.common_lib.test_utils import mock
from autotest_lib.frontend.afe import frontend_test_utils, models as afe_models
from autotest_lib.frontend.afe import model_attributes as afe_model_attributes
from autotest_lib.frontend.shared import rest_client
from autotest_lib.frontend.planner import models, execution_engine, support
from autotest_lib.frontend.planner import model_attributes


class MockObject(object):
    """
    Empty mock object class, so that setattr() works on all names
    """
    pass


class MockAfeRest(object):
    jobs = MockObject()
    execution_info = MockObject()
    queue_entries_request = MockObject()


class MockRestJobs(object):
    def __init__(self, total_results):
        self.total_results = total_results


class MockExecutionInfo(object):
    execution_info = {}


class MockQueueEntriesRequest(object):
    queue_entries = object()


class MockExecutionEngine(execution_engine.ExecutionEngine):
    _planner_rpc = MockObject()
    _tko_rpc = object()
    _plan_id = object()
    _server = object()
    _afe_rest = MockAfeRest()
    _label_name = object()
    _owner = object()


    def __init__(self, *args, **kwargs):
        pass


class MockTestPlanController(support.TestPlanController):
    def __init__(self, *args, **kwargs):
        super(MockTestPlanController, self).__init__(machine=None,
                                                     test_alias=None)


class ExecutionEngineTest(unittest.TestCase,
                          frontend_test_utils.FrontendTestMixin):
    def setUp(self):
        self._frontend_common_setup()
        self.engine = MockExecutionEngine()


    def tearDown(self):
        self._frontend_common_teardown()


    def _setup_test_initialize_plan(self):
        self.god.stub_function(self.engine._planner_rpc, 'run')
        self.god.stub_function(self.engine._afe_rest.jobs, 'get')
        self.god.stub_function(self.engine, '_wait_for_initialization')


    def test_initialize_plan_new_plan(self):
        self._setup_test_initialize_plan()
        self.god.stub_function(self.engine, '_launch_set_atomic_group_job')

        self.engine._planner_rpc.run.expect_call(
                'get_plan', id=self.engine._plan_id).and_return(
                {'name': 'plan'})
        self.engine._afe_rest.jobs.get.expect_call(
                name='plan_set_atomic_group').and_return(MockRestJobs(None))
        self.engine._launch_set_atomic_group_job.expect_call(
                'plan_set_atomic_group')
        self.engine._wait_for_initialization.expect_call()

        self.engine._initialize_plan()
        self.god.check_playback


    def test_initialize_plan_existing(self):
        self._setup_test_initialize_plan()

        self.engine._planner_rpc.run.expect_call(
                'get_plan', id=self.engine._plan_id).and_return(
                {'name': 'plan'})
        self.engine._afe_rest.jobs.get.expect_call(
                name='plan_set_atomic_group').and_return(MockRestJobs(object()))
        self.engine._wait_for_initialization.expect_call()

        self.engine._initialize_plan()
        self.god.check_playback


    def _setup_test_launch_atomic_group_job(self, name):
        DUMMY_CONTROL = '%(server)r %(label_name)r %(plan_id)r'
        DUMMY_EXECUTION_INFO = MockExecutionInfo()
        DUMMY_QUEUE_ENTRIES_REQUEST = MockQueueEntriesRequest()

        self.god.stub_function(self.engine._planner_rpc, 'run')
        self.god.stub_function(self.engine._afe_rest.execution_info, 'get')
        self.god.stub_function(
                self.engine._afe_rest.queue_entries_request, 'get')

        self.engine._planner_rpc.run.expect_call(
                'get_hosts', plan_id=self.engine._plan_id).and_return(
                self.hosts)
        self.engine._planner_rpc.run.expect_call(
                'get_atomic_group_control_file').and_return(DUMMY_CONTROL)
        self.engine._afe_rest.execution_info.get.expect_call().and_return(
                DUMMY_EXECUTION_INFO)
        self.engine._afe_rest.queue_entries_request.get.expect_call(
                hosts=self.hosts).and_return(DUMMY_QUEUE_ENTRIES_REQUEST)

        control_file = DUMMY_CONTROL % dict(server=self.engine._server,
                                            label_name=self.engine._label_name,
                                            plan_id=self.engine._plan_id)
        DUMMY_EXECUTION_INFO.execution_info = {
                'control_file': control_file,
                'cleanup_before_job': afe_model_attributes.RebootBefore.NEVER,
                'cleanup_after_job': afe_model_attributes.RebootAfter.NEVER,
                'run_verify': False,
                'machines_per_execution': len(self.hosts)}

        job_req = {'name': name,
                   'owner': self.engine._owner,
                   'execution_info': DUMMY_EXECUTION_INFO.execution_info,
                   'queue_entries': DUMMY_QUEUE_ENTRIES_REQUEST.queue_entries}

        return job_req


    def test_launch_atomic_group_job(self):
        job_req = self._setup_test_launch_atomic_group_job('atomic_group_job')
        self.god.stub_function(self.engine._afe_rest.jobs, 'post')

        self.engine._afe_rest.jobs.post.expect_call(job_req)

        self.engine._launch_set_atomic_group_job('atomic_group_job')
        self.god.check_playback()


    def _setup_mock_controller(self, controller_options):
        mock_controller = MockTestPlanController()
        for key, value in controller_options.iteritems():
            setattr(mock_controller, key, value)
        self.god.stub_with(support, 'TestPlanController',
                           lambda *args, **kwargs : mock_controller)
        return mock_controller


    def _test_process_finished_runs_helper(self, status, should_block=False,
                                           controller_options={}):
        Status = model_attributes.TestRunStatus
        TEST_RUN_ID = object()
        TKO_TEST_ID = object()
        HOST_ID = object()

        mock_controller = self._setup_mock_controller(controller_options)

        self.god.stub_function(self.engine._planner_rpc, 'run')
        self.god.stub_function(self.engine, '_run_execute_after')

        test_run = {'id': TEST_RUN_ID,
                    'host': {'host': self.hosts[0].hostname,
                             'id': HOST_ID},
                    'test_job': {'test_config': {'alias': 'test_alias'}},
                    'tko_test': TKO_TEST_ID,
                    'status': status}

        self.engine._planner_rpc.run.expect_call(
                'get_test_runs',
                plan__id=self.engine._plan_id,
                status__in=(Status.PASSED, Status.FAILED),
                finalized=False).and_return([test_run])
        self.engine._run_execute_after.expect_call(
                mock_controller, tko_test_id=TKO_TEST_ID,
                success=(status == Status.PASSED))
        if should_block:
            self.engine._planner_rpc.run.expect_call('modify_host', id=HOST_ID,
                                                     blocked=True)
        self.engine._planner_rpc.run.expect_call('modify_test_run',
                                                 id=TEST_RUN_ID, finalized=True)

        self.engine._process_finished_runs()

        self.god.check_playback()


    def test_process_finished_runs_pass(self):
        self._test_process_finished_runs_helper(
                model_attributes.TestRunStatus.PASSED)


    def test_process_finished_runs_fail(self):
        self._test_process_finished_runs_helper(
                model_attributes.TestRunStatus.FAILED, should_block=True)


    def test_process_finished_runs_fail_unblock(self):
        self._test_process_finished_runs_helper(
                model_attributes.TestRunStatus.FAILED, should_block=False,
                controller_options={'_unblock': True})


    def _test_schedule_new_runs_helper(self, complete=False, should_skip=False,
                                       controller_options={}):
        TEST_CONFIG_ID = object()

        self.god.stub_function(self.engine._planner_rpc, 'run')
        self.god.stub_function(self.engine, '_run_execute_before')

        result = {'complete': complete,
                  'next_configs': [{'next_test_config_id': TEST_CONFIG_ID,
                                    'host': self.hosts[0].hostname,
                                    'next_test_config_alias': object()}]}

        mock_controller = self._setup_mock_controller(controller_options)

        self.engine._planner_rpc.run.expect_call(
                'get_next_test_configs',
                plan_id=self.engine._plan_id).and_return(result)

        if not complete:
            self.engine._run_execute_before.expect_call(mock_controller)

            if should_skip:
                self.engine._planner_rpc.run.expect_call(
                        'skip_test', test_config_id=TEST_CONFIG_ID,
                        hostname=self.hosts[0].hostname)
            else:
                self.god.stub_function(self.engine, '_run_job')
                self.engine._run_job.expect_call(
                        hostname=self.hosts[0].hostname,
                        test_config_id=TEST_CONFIG_ID,
                        cleanup_before_job=mock_controller._reboot_before,
                        cleanup_after_job=mock_controller._reboot_after,
                        run_verify=mock_controller._run_verify)

        self.engine._schedule_new_runs()

        self.god.check_playback()


    def test_schedule_new_runs(self):
        self._test_schedule_new_runs_helper()


    def test_schedule_new_runs_complete(self):
        self._test_schedule_new_runs_helper(complete=True)


    def test_schedule_new_runs_skip(self):
        self._test_schedule_new_runs_helper(should_skip=True,
                                            controller_options={'_skip': True})


    def test_run_global_support(self):
        self._ran_global_support = False
        support = """
def test_global_support(controller):
    controller._ran_global_support = True
"""

        DUMMY_PLAN = {'support': support}

        self.god.stub_function(self.engine._planner_rpc, 'run')

        self.engine._planner_rpc.run.expect_call(
                'get_plan', id=self.engine._plan_id).and_return(DUMMY_PLAN)

        self.engine._run_global_support(controller=self,
                                        function_name='test_global_support')

        self.assertTrue(self._ran_global_support)
        self.god.check_playback()


if __name__ == '__main__':
    unittest.main()
