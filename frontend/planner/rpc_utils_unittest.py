#!/usr/bin/python

import unittest
import common
from autotest_lib.frontend import setup_django_environment
from autotest_lib.frontend.planner import planner_test_utils
from autotest_lib.frontend.afe import model_logic, models as afe_models
from autotest_lib.frontend.afe import rpc_interface as afe_rpc_interface
from autotest_lib.frontend.planner import models, rpc_utils
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
                test_config.id,
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


if __name__ == '__main__':
    unittest.main()
