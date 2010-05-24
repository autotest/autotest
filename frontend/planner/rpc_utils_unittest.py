#!/usr/bin/python

import unittest
import common
from autotest_lib.frontend import setup_django_environment
from autotest_lib.frontend import setup_test_environment
from autotest_lib.frontend.afe import model_logic, models as afe_models
from autotest_lib.frontend.planner import planner_test_utils, model_attributes
from autotest_lib.frontend.planner import models, rpc_utils, failure_actions
from autotest_lib.frontend.tko import models as tko_models
from autotest_lib.client.common_lib import utils, host_queue_entry_states


class RpcUtilsTest(unittest.TestCase,
                   planner_test_utils.PlannerTestMixin):
    def setUp(self):
        self._planner_common_setup()


    def tearDown(self):
        self._planner_common_teardown()


    def test_create_plan_label(self):
        label, group = self._create_label_helper()

        label.delete()
        group.invalid = True
        group.save()

        label, group = self._create_label_helper()

        self.assertRaises(model_logic.ValidationError,
                          rpc_utils.create_plan_label, self._plan)


    def _create_label_helper(self):
        label = rpc_utils.create_plan_label(self._plan)
        group = afe_models.AtomicGroup.objects.get(
                name=rpc_utils.PLANNER_ATOMIC_GROUP_NAME)
        self.assertFalse(group.invalid)
        self.assertEqual(label.atomic_group, group)

        return (label, group)


    def test_lazy_load(self):
        self.god.stub_function(utils, 'read_file')

        DUMMY_PATH_1 = object()
        DUMMY_PATH_2 = object()
        DUMMY_FILE_1 = object()
        DUMMY_FILE_2 = object()

        utils.read_file.expect_call(DUMMY_PATH_1).and_return(DUMMY_FILE_1)
        self.assertEqual(DUMMY_FILE_1, rpc_utils.lazy_load(DUMMY_PATH_1))
        self.god.check_playback()

        # read_file should not be called again for this path
        self.assertEqual(DUMMY_FILE_1, rpc_utils.lazy_load(DUMMY_PATH_1))
        self.god.check_playback()

        # new file; read_file must be called again
        utils.read_file.expect_call(DUMMY_PATH_2).and_return(DUMMY_FILE_2)
        self.assertEqual(DUMMY_FILE_2, rpc_utils.lazy_load(DUMMY_PATH_2))
        self.god.check_playback()


    def test_update_hosts_table(self):
        label = self.labels[3]
        default_hosts = set(self._plan.hosts.all())

        rpc_utils.update_hosts_table(self._plan)
        self.assertEqual(default_hosts, set(self._plan.hosts.all()))
        self.assertEqual(set(), self._get_added_by_label_hosts())

        self._plan.host_labels.add(label)
        rpc_utils.update_hosts_table(self._plan)
        self.assertEqual(default_hosts.union(label.host_set.all()),
                         set(self._plan.hosts.all()))
        self.assertEqual(set(label.host_set.all()),
                         self._get_added_by_label_hosts())

        self._plan.host_labels.remove(label)
        rpc_utils.update_hosts_table(self._plan)
        self.assertEqual(default_hosts, set(self._plan.hosts.all()))
        self.assertEqual(set(), self._get_added_by_label_hosts())


    def _get_added_by_label_hosts(self):
        return set(host.host for host in models.Host.objects.filter(
                plan=self._plan, added_by_label=True))


    def test_compute_next_test_config(self):
        self._setup_active_plan()
        test_config = models.TestConfig.objects.create(
                plan=self._plan, alias='config2', control_file=self._control,
                execution_order=2, estimated_runtime=1)

        self.assertEqual(1, self._afe_job.hostqueueentry_set.count())
        self.assertEqual(
                None, rpc_utils.compute_next_test_config(self._plan,
                                                         self._planner_host))
        self.assertFalse(self._planner_host.complete)

        hqe = self._afe_job.hostqueueentry_set.all()[0]
        hqe.status = host_queue_entry_states.Status.COMPLETED
        hqe.save()

        self.assertEqual(
                test_config,
                rpc_utils.compute_next_test_config(self._plan,
                                                   self._planner_host))
        self.assertFalse(self._planner_host.complete)

        afe_job = self._create_job(hosts=(1,))
        planner_job = models.Job.objects.create(plan=self._plan,
                                                  test_config=test_config,
                                                  afe_job=afe_job)

        self.assertEqual(
                None, rpc_utils.compute_next_test_config(self._plan,
                                                         self._planner_host))
        self.assertFalse(self._planner_host.complete)

        hqe = afe_job.hostqueueentry_set.all()[0]
        hqe.status = host_queue_entry_states.Status.COMPLETED
        hqe.save()

        self.assertEqual(
                None, rpc_utils.compute_next_test_config(self._plan,
                                                         self._planner_host))
        self.assertTrue(self._planner_host.complete)


    def test_process_failure(self):
        self._setup_active_plan()
        tko_test = tko_models.Test.objects.create(job=self._tko_job,
                                                  machine=self._tko_machine,
                                                  kernel=self._tko_kernel,
                                                  status=self._running_status)
        failure = models.TestRun.objects.create(
                plan=self._plan,
                test_job=self._planner_job,
                tko_test=tko_test,
                host=self._planner_host,
                status=model_attributes.TestRunStatus.FAILED,
                finalized=True, seen=False, triaged=False)
        host_action = failure_actions.HostAction.UNBLOCK
        test_action = failure_actions.TestAction.SKIP
        labels = ['label1', 'label2']
        keyvals = {'key1': 'value1',
                   'key2': 'value2'}
        bugs = ['bug1', 'bug2']
        reason = 'overriden reason'
        invalidate = True

        self.god.stub_function(rpc_utils, '_process_host_action')
        self.god.stub_function(rpc_utils, '_process_test_action')

        rpc_utils._process_host_action.expect_call(self._planner_host,
                                                   host_action)
        rpc_utils._process_test_action.expect_call(self._planner_job,
                                                   test_action)

        rpc_utils.process_failure(
                failure_id=failure.id, host_action=host_action,
                test_action=test_action, labels=labels, keyvals=keyvals,
                bugs=bugs, reason=reason, invalidate=invalidate)
        failure = models.TestRun.objects.get(id=failure.id)

        self.assertEqual(
                set(failure.tko_test.testlabel_set.all()),
                set(tko_models.TestLabel.objects.filter(name__in=labels)))
        self.assertEqual(
                set(failure.tko_test.job.jobkeyval_set.all()),
                set(tko_models.JobKeyval.objects.filter(
                        key__in=keyvals.iterkeys())))
        self.assertEqual(set(failure.bugs.all()),
                         set(models.Bug.objects.filter(external_uid__in=bugs)))
        self.assertEqual(failure.tko_test.reason, reason)
        self.assertEqual(failure.invalidated, invalidate)
        self.assertTrue(failure.seen)
        self.assertTrue(failure.triaged)
        self.god.check_playback()


    def _replace_site_process_host_action(self, replacement):
        self.god.stub_function(utils, 'import_site_function')
        utils.import_site_function.expect_any_call().and_return(replacement)


    def _remove_site_process_host_action(self):
        def _site_process_host_action_dummy(host, action):
            return False
        self._replace_site_process_host_action(_site_process_host_action_dummy)


    def test_process_host_action_block(self):
        self._remove_site_process_host_action()
        host = models.Host.objects.create(plan=self._plan, host=self.hosts[0],
                                          blocked=False)
        assert not host.blocked

        rpc_utils._process_host_action(host, failure_actions.HostAction.BLOCK)
        host = models.Host.objects.get(id=host.id)

        self.assertTrue(host.blocked)
        self.god.check_playback()


    def test_process_host_action_unblock(self):
        self._remove_site_process_host_action()
        host = models.Host.objects.create(plan=self._plan, host=self.hosts[0],
                                          blocked=True)
        assert host.blocked

        rpc_utils._process_host_action(host, failure_actions.HostAction.UNBLOCK)
        host = models.Host.objects.get(id=host.id)

        self.assertFalse(host.blocked)
        self.god.check_playback()


    def test_process_host_action_site(self):
        self._remove_site_process_host_action
        action = object()
        failure_actions.HostAction.values.append(action)
        host = models.Host.objects.create(plan=self._plan, host=self.hosts[0])

        self.assertRaises(AssertionError, rpc_utils._process_host_action,
                          host, action)
        self.god.check_playback()

        self._called = False
        def _site_process_host_action(host, action):
            self._called = True
            return True
        self._replace_site_process_host_action(_site_process_host_action)

        rpc_utils._process_host_action(host, action)

        self.assertTrue(self._called)
        self.god.check_playback()


    def test_process_test_action_skip(self):
        self._setup_active_plan()
        planner_job = self._planner_job
        assert not planner_job.requires_rerun

        rpc_utils._process_test_action(planner_job,
                                       failure_actions.TestAction.SKIP)
        planner_job = models.Job.objects.get(id=planner_job.id)

        self.assertFalse(planner_job.requires_rerun)


    def test_process_test_action_rerun(self):
        self._setup_active_plan()
        planner_job = self._planner_job
        assert not planner_job.requires_rerun

        rpc_utils._process_test_action(planner_job,
                                       failure_actions.TestAction.RERUN)
        planner_job = models.Job.objects.get(id=planner_job.id)

        self.assertTrue(planner_job.requires_rerun)


    def test_set_additional_parameters(self):
        hostname_regex = 'host[0-9]'
        param_type = model_attributes.AdditionalParameterType.VERIFY
        param_values = {'key1': 'value1',
                        'key2': []}

        additional_parameters = {'hostname_regex': hostname_regex,
                                 'param_type': param_type,
                                 'param_values': param_values}

        rpc_utils.set_additional_parameters(self._plan, [additional_parameters])

        additional_parameters_query = (
                models.AdditionalParameter.objects.filter(plan=self._plan))
        self.assertEqual(additional_parameters_query.count(), 1)

        additional_parameter = additional_parameters_query[0]
        self.assertEqual(additional_parameter.hostname_regex, hostname_regex)
        self.assertEqual(additional_parameter.param_type, param_type)
        self.assertEqual(additional_parameter.application_order, 0)

        values_query = additional_parameter.additionalparametervalue_set.all()
        self.assertEqual(values_query.count(), 2)

        value_query1 = values_query.filter(key='key1')
        value_query2 = values_query.filter(key='key2')
        self.assertEqual(value_query1.count(), 1)
        self.assertEqual(value_query2.count(), 1)

        self.assertEqual(value_query1[0].value, repr('value1'))
        self.assertEqual(value_query2[0].value, repr([]))


    def test_get_wrap_arguments(self):
        hostname_regex = '.*'
        param_type = model_attributes.AdditionalParameterType.VERIFY

        additional_param = models.AdditionalParameter.objects.create(
                plan=self._plan, hostname_regex=hostname_regex,
                param_type=param_type, application_order=0)
        models.AdditionalParameterValue.objects.create(
                additional_parameter=additional_param,
                key='key1', value=repr('value1'))
        models.AdditionalParameterValue.objects.create(
                additional_parameter=additional_param,
                key='key2', value=repr([]))

        actual = rpc_utils.get_wrap_arguments(self._plan, 'host', param_type)
        expected = {'key1': repr('value1'),
                    'key2': repr([])}

        self.assertEqual(actual, expected)


    def test_compute_test_config_status_scheduled(self):
        self._setup_active_plan()
        self._planner_job.delete()

        self.assertEqual(
                rpc_utils.compute_test_config_status(self._planner_host),
                rpc_utils.ComputeTestConfigStatusResult.SCHEDULED)


    def test_compute_test_config_status_running(self):
        self._setup_active_plan()
        self.god.stub_function(models.Job, 'active')
        models.Job.active.expect_call().and_return(True)

        self.assertEqual(
                rpc_utils.compute_test_config_status(self._planner_host),
                rpc_utils.ComputeTestConfigStatusResult.RUNNING)
        self.god.check_playback()


    def test_compute_test_config_status_good(self):
        self._setup_active_plan()
        tko_test = self._tko_job.test_set.create(kernel=self._tko_kernel,
                                                 status=self._good_status,
                                                 machine=self._tko_machine)
        self._plan.testrun_set.create(test_job=self._planner_job,
                                      tko_test=tko_test,
                                      host=self._planner_host)
        self._planner_host.complete = True
        self._planner_host.save()
        self.god.stub_function(models.Job, 'active')
        models.Job.active.expect_call().and_return(False)

        self.assertEqual(
                rpc_utils.compute_test_config_status(self._planner_host),
                rpc_utils.ComputeTestConfigStatusResult.PASS)
        self.god.check_playback()


    def test_compute_test_config_status_bad(self):
        self._setup_active_plan()
        tko_test = self._tko_job.test_set.create(kernel=self._tko_kernel,
                                                 status=self._fail_status,
                                                 machine=self._tko_machine)
        self._plan.testrun_set.create(test_job=self._planner_job,
                                      tko_test=tko_test,
                                      host=self._planner_host)
        self._planner_host.complete = True
        self._planner_host.save()
        self.god.stub_function(models.Job, 'active')
        models.Job.active.expect_call().and_return(False)

        self.assertEqual(
                rpc_utils.compute_test_config_status(self._planner_host),
                rpc_utils.ComputeTestConfigStatusResult.FAIL)
        self.god.check_playback()


if __name__ == '__main__':
    unittest.main()
