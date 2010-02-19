#!/usr/bin/python

import unittest
import common
from autotest_lib.frontend import setup_django_environment
from autotest_lib.frontend.planner import planner_test_utils
from autotest_lib.frontend.afe import model_logic
from autotest_lib.frontend.afe import models as afe_models
from autotest_lib.frontend.planner import rpc_interface, models, rpc_utils


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


if __name__ == '__main__':
    unittest.main()
