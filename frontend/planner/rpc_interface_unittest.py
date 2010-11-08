#!/usr/bin/python

import unittest
import common
from autotest_lib.frontend import setup_django_environment
from autotest_lib.frontend import setup_test_environment
from autotest_lib.frontend.planner import planner_test_utils, model_attributes
from autotest_lib.frontend.planner import rpc_interface, models, rpc_utils
from autotest_lib.frontend.planner import failure_actions
from autotest_lib.frontend.afe import model_logic, models as afe_models
from autotest_lib.frontend.afe import rpc_interface as afe_rpc_interface
from autotest_lib.frontend.tko import models as tko_models


class DummyTestConfig(object):
    def __init__(self):
        self.id = object()
        self.alias = object()


class RpcInterfaceTest(unittest.TestCase,
                       planner_test_utils.PlannerTestMixin):
    def setUp(self):
        self._planner_common_setup()
        self.god.stub_function(rpc_utils, 'start_plan')


    def tearDown(self):
        self._planner_common_teardown()


    def test_submit_plan_success(self):
        hosts = ('host1', 'host2')
        plan_name = self._PLAN_NAME + '2'

        rpc_utils.start_plan.expect_any_call()
        rpc_interface.submit_plan(plan_name, hosts, ('label1',), ())

        plan = models.Plan.objects.get(name=plan_name)
        self.assertEqual(
                set(afe_models.Host.objects.filter(hostname__in=hosts)),
                set(plan.hosts.all()))

        self.assertEqual(1, plan.host_labels.all().count())
        self.assertEqual(afe_models.Label.objects.get(name='label1'),
                         plan.host_labels.all()[0])
        self.god.check_playback()


    def test_submit_plan_duplicate(self):
        self.assertRaises(
                model_logic.ValidationError, rpc_interface.submit_plan,
                self._PLAN_NAME, (), (), ())


    def test_submit_plan_bad_host(self):
        self.assertRaises(
                model_logic.ValidationError, rpc_interface.submit_plan,
                self._PLAN_NAME + '2', ('fakehost'), (), ())


    def test_submit_plan_bad_label(self):
        self.assertRaises(
                model_logic.ValidationError, rpc_interface.submit_plan,
                self._PLAN_NAME + '2', (), ('fakelabel'), ())


    def test_get_hosts(self):
        hosts = rpc_interface.get_hosts(self._PLAN_NAME)
        self.assertEqual(set(('host1', 'host2')), set(hosts))

        afe_models.Host.objects.get(hostname='host3').labels.add(
                afe_models.Label.objects.get(name='label1'))

        hosts = rpc_interface.get_hosts(self._PLAN_NAME)
        self.assertEqual(set(('host1', 'host2', 'host3')), set(hosts))

        afe_models.Host.objects.get(hostname='host3').labels.clear()

        hosts = rpc_interface.get_hosts(self._PLAN_NAME)
        self.assertEqual(set(('host1', 'host2')), set(hosts))


    def test_get_next_test_configs(self):
        DUMMY_CONFIGS = {'host1': DummyTestConfig(),
                         'host2': DummyTestConfig()}
        DUMMY_COMPLETE = object()
        self.god.stub_function(rpc_utils, 'compute_next_test_config')

        for host in models.Host.objects.filter(plan=self._plan):
            rpc_utils.compute_next_test_config.expect_call(
                    self._plan, host).and_return(
                    DUMMY_CONFIGS[host.host.hostname])

        def _dummy_check_for_completion(plan):
            plan.complete = DUMMY_COMPLETE
        rpc_utils.check_for_completion = _dummy_check_for_completion

        result = rpc_interface.get_next_test_configs(self._plan.id)

        self.god.check_playback()
        self.assertEqual(result['complete'], DUMMY_COMPLETE)
        for config in result['next_configs']:
            self.assertTrue(config['host'] in DUMMY_CONFIGS)
            self.assertEqual(config['next_test_config_id'],
                             DUMMY_CONFIGS[config['host']].id)
            self.assertEqual(config['next_test_config_alias'],
                             DUMMY_CONFIGS[config['host']].alias)


    def test_update_test_runs(self):
        self._setup_active_plan()

        self.god.stub_function(rpc_utils, 'compute_test_run_status')
        self.god.stub_function(rpc_utils, 'add_test_run')

        # No TKO tests
        self.assertEqual([], rpc_interface.update_test_runs(self._plan.id))
        self.god.check_playback()

        # active TKO test
        tko_test = tko_models.Test.objects.create(job=self._tko_job,
                                                  machine=self._tko_machine,
                                                  kernel=self._tko_kernel,
                                                  status=self._running_status)

        rpc_utils.compute_test_run_status.expect_call(
                self.RUNNING_STATUS_WORD).and_return(
                model_attributes.TestRunStatus.ACTIVE)
        rpc_utils.add_test_run.expect_call(
                self._plan, self._planner_job, tko_test, self._hostname,
                model_attributes.TestRunStatus.ACTIVE)
        self.assertEqual(rpc_interface.update_test_runs(self._plan.id),
                         [{'status': model_attributes.TestRunStatus.ACTIVE,
                           'tko_test_idx': tko_test.test_idx,
                           'hostname': self._hostname}])
        self.god.check_playback()
        test_run = models.TestRun.objects.create(
                plan=self._plan, test_job=self._planner_job,
                tko_test=tko_test, host=self._planner_host,
                status=model_attributes.TestRunStatus.ACTIVE)

        # no change to TKO test
        rpc_utils.compute_test_run_status.expect_call(
                self.RUNNING_STATUS_WORD).and_return(
                model_attributes.TestRunStatus.ACTIVE)
        self.assertEqual([], rpc_interface.update_test_runs(self._plan.id))
        self.god.check_playback()

        # TKO test is now complete, passed
        tko_test.status = self._good_status
        tko_test.save()

        rpc_utils.compute_test_run_status.expect_call(
                self.GOOD_STATUS_WORD).and_return(
                model_attributes.TestRunStatus.PASSED)
        rpc_utils.add_test_run.expect_call(
                self._plan, self._planner_job, tko_test, self._hostname,
                model_attributes.TestRunStatus.PASSED)
        self.assertEqual(rpc_interface.update_test_runs(self._plan.id),
                         [{'status': model_attributes.TestRunStatus.PASSED,
                           'tko_test_idx': tko_test.test_idx,
                           'hostname': self._hostname}])
        self.god.check_playback()


    def test_get_machine_view_data(self):
        self._setup_active_plan()

        host1_expected = {'machine': 'host1',
                          'status': 'Running',
                          'tests_run': [],
                          'bug_ids': []}
        host2_expected = {'machine': 'host2',
                          'status': 'Running',
                          'tests_run': [],
                          'bug_ids': []}

        expected = (host1_expected, host2_expected)
        actual = rpc_interface.get_machine_view_data(plan_id=self._plan.id)
        self.assertEqual(sorted(actual), sorted(expected))

        # active TKO test
        tko_test = tko_models.Test.objects.create(job=self._tko_job,
                                                  test='test',
                                                  machine=self._tko_machine,
                                                  kernel=self._tko_kernel,
                                                  status=self._running_status)
        testrun = models.TestRun.objects.create(plan=self._plan,
                                                test_job=self._planner_job,
                                                host=self._planner_host,
                                                tko_test=tko_test,
                                                finalized=True)

        host1_expected['tests_run'] = [{'test_name': 'test',
                                        'status': self._running_status.word}]
        actual = rpc_interface.get_machine_view_data(plan_id=self._plan.id)
        self.assertEqual(sorted(actual), sorted(expected))

        # TKO test complete, passed, with bug filed
        tko_test.status = self._good_status
        tko_test.save()
        bug = models.Bug.objects.create(external_uid='bug')
        testrun.bugs.add(bug)

        host1_expected['tests_run'] = [{'test_name': 'test',
                                        'status': self._good_status.word}]
        host1_expected['bug_ids'] = ['bug']
        actual = rpc_interface.get_machine_view_data(plan_id=self._plan.id)
        self.assertEqual(sorted(actual), sorted(expected))


    def test_generate_test_config(self):
        control = {'control_file': object(),
                   'is_server': object()}
        test = 'test'
        alias = 'test alias'
        estimated_runtime = object()

        self.god.stub_function(afe_rpc_interface, 'generate_control_file')
        afe_rpc_interface.generate_control_file.expect_call(
                tests=[test]).and_return(control)

        result = rpc_interface.generate_test_config(
                alias=alias, afe_test_name=test,
                estimated_runtime=estimated_runtime)

        self.assertEqual(result['alias'], 'test_alias')
        self.assertEqual(result['control_file'], control['control_file'])
        self.assertEqual(result['is_server'], control['is_server'])
        self.assertEqual(result['estimated_runtime'], estimated_runtime)
        self.god.check_playback()


    def _test_get_overview_data_helper(self, stage):
        self._setup_active_plan()
        self.god.stub_function(rpc_utils, 'compute_test_config_status')
        rpc_utils.compute_test_config_status.expect_call(
                self._plan.host_set.get(host=self.hosts[0])).and_return(None)
        rpc_utils.compute_test_config_status.expect_call(
                self._plan.host_set.get(host=self.hosts[1])).and_return(None)

        data = {'test_configs': [{'complete': 0, 'estimated_runtime': 1}],
                'bugs': [],
                'machines': [{'hostname': self.hosts[0].hostname,
                              'status': 'Running',
                              'passed': None},
                             {'hostname': self.hosts[1].hostname,
                              'status': 'Running',
                              'passed': None}]}
        if stage < 1:
            return {self._plan.name: data}

        tko_test = self._tko_job.test_set.create(kernel=self._tko_kernel,
                                                 machine=self._tko_machine,
                                                 status=self._fail_status)
        test_run = self._plan.testrun_set.create(test_job=self._planner_job,
                                                 tko_test=tko_test,
                                                 host=self._planner_host)
        self._afe_job.hostqueueentry_set.update(complete=True)
        self._planner_host.complete = True
        self._planner_host.save()
        test_run.bugs.create(external_uid='bug')
        data['bugs'] = ['bug']
        data['test_configs'][0]['complete'] = 1
        data['machines'][0]['status'] = 'Finished'
        return {self._plan.name: data}


    def test_get_overview_data_no_progress(self):
        self.assertEqual(self._test_get_overview_data_helper(0),
                         rpc_interface.get_overview_data([self._plan.id]))
        self.god.check_playback()


    def test_get_overview_data_one_finished_with_bug(self):
        self.assertEqual(self._test_get_overview_data_helper(1),
                         rpc_interface.get_overview_data([self._plan.id]))
        self.god.check_playback()


    def _test_get_test_view_data_helper(self, stage):
        self._setup_active_plan()
        self.god.stub_function(rpc_utils, 'compute_test_config_status')
        hosts = self._plan.host_set.filter(host__in=self.hosts[0:2])
        rpc_utils.compute_test_config_status.expect_call(
                hosts[0], self._test_config).and_return(None)

        data = {'total_machines': 2,
                'machine_status': {'host1': None,
                                   'host2': None},
                'total_runs': 1,
                'total_passes': 0,
                'bugs': []}
        if stage < 1:
            rpc_utils.compute_test_config_status.expect_call(
                    hosts[1], self._test_config).and_return(None)
            return {self._test_config.alias: data}

        fail_status = rpc_utils.ComputeTestConfigStatusResult.FAIL
        rpc_utils.compute_test_config_status.expect_call(
                hosts[1], self._test_config).and_return(fail_status)
        tko_test = self._tko_job.test_set.create(kernel=self._tko_kernel,
                                                 machine=self._tko_machine,
                                                 status=self._fail_status)
        test_run = self._plan.testrun_set.create(test_job=self._planner_job,
                                                 tko_test=tko_test,
                                                 host=self._planner_host)
        self._afe_job.hostqueueentry_set.update(complete=True)

        test_run.bugs.create(external_uid='bug')

        data['machine_status']['host2'] = fail_status
        data['bugs'] = ['bug']
        return {self._test_config.alias: data}


    def test_get_test_view_data_no_progress(self):
        self.assertEqual(self._test_get_test_view_data_helper(0),
                         rpc_interface.get_test_view_data(self._plan.id))
        self.god.check_playback()


    def test_get_test_view_data_one_failed_with_bug(self):
        self.assertEqual(self._test_get_test_view_data_helper(1),
                         rpc_interface.get_test_view_data(self._plan.id))
        self.god.check_playback()


if __name__ == '__main__':
    unittest.main()
