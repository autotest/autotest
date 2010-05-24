#!/usr/bin/python

import unittest
import common
from autotest_lib.frontend import setup_django_environment
from autotest_lib.frontend.afe import frontend_test_utils, rpc_utils
from autotest_lib.frontend.tko import models as tko_models
from autotest_lib.frontend.planner import models, model_attributes
from autotest_lib.frontend.planner import planner_test_utils


class ModelWithHashTestBase(frontend_test_utils.FrontendTestMixin):
    def setUp(self):
        self._frontend_common_setup(fill_data=False)


    def tearDown(self):
        self._frontend_common_teardown()


    def _model_class(self):
        raise NotImplementedError('Subclasses must override _model_class()')


    def _test_data(self):
        raise NotImplementedError('Subclasses must override _test_data()')


    def test_disallowed_operations(self):
        def _call_create():
            self._model_class().objects.create(**self._test_data())
        self.assertRaises(Exception, _call_create)

        model = self._model_class().objects.get_or_create(
                **self._test_data())[0]
        self.assertRaises(Exception, model.save)


    def test_hash_field(self):
        model = self._model_class().objects.get_or_create(
                **self._test_data())[0]
        self.assertNotEqual(model.id, None)
        self.assertEqual(self._model_class()._compute_hash(**self._test_data()),
                         model.the_hash)


class ControlFileTest(ModelWithHashTestBase, unittest.TestCase):
    def _model_class(self):
        return models.ControlFile


    def _test_data(self):
        return {'contents' : 'test_control'}


class KeyValTest(ModelWithHashTestBase, unittest.TestCase):
    def _model_class(self):
        return models.KeyVal


    def _test_data(self):
        return {'key' : 'test_key',
                'value' : 'test_value'}


class AdditionalParameterTest(frontend_test_utils.FrontendTestMixin,
                              unittest.TestCase):
    def setUp(self):
        self._frontend_common_setup()
        self.plan = models.Plan.objects.create(name='plan')
        self.param_type = model_attributes.AdditionalParameterType.VERIFY

    def tearDown(self):
        self._frontend_common_teardown()


    def test_find_applicable_control_parameter_match(self):
        parameter = models.AdditionalParameter.objects.create(
                plan=self.plan, hostname_regex='host.*',
                param_type=self.param_type, application_order=0)
        found = models.AdditionalParameter.find_applicable_additional_parameter(
                plan=self.plan, hostname='host1', param_type=self.param_type)

        self.assertEqual(parameter, found)


    def test_find_applicable_additional_parameter_ordered(self):
        additional1 = models.AdditionalParameter.objects.create(
                plan=self.plan, hostname_regex='host.*',
                param_type=self.param_type, application_order=0)
        additional2 = models.AdditionalParameter.objects.create(
                plan=self.plan, hostname_regex='.*',
                param_type=self.param_type, application_order=1)

        found1 = (
                models.AdditionalParameter.find_applicable_additional_parameter(
                        plan=self.plan, hostname='host1',
                        param_type=self.param_type))
        found2 = (
                models.AdditionalParameter.find_applicable_additional_parameter(
                        plan=self.plan, hostname='other',
                        param_type=self.param_type))

        self.assertEqual(additional1, found1)
        self.assertEqual(additional2, found2)


    def test_find_applicable_additional_parameter_no_match(self):
        models.AdditionalParameter.objects.create(
                plan=self.plan, hostname_regex='host.*',
                param_type=self.param_type, application_order=0)
        found = models.AdditionalParameter.find_applicable_additional_parameter(
                plan=self.plan, hostname='other', param_type=self.param_type)

        self.assertEqual(None, found)


class JobTest(planner_test_utils.PlannerTestMixin,
              unittest.TestCase):
    def setUp(self):
        self._planner_common_setup()
        self._setup_active_plan()


    def tearDown(self):
        self._planner_common_teardown()


    def test_active(self):
        self.assertEqual(True, self._planner_job.active())
        self._afe_job.hostqueueentry_set.update(complete=True)
        self.assertEqual(False, self._planner_job.active())


    def test_all_tests_passed_active(self):
        self.assertEqual(True, self._planner_job.active())
        self.assertEqual(False, self._planner_job.all_tests_passed())


    def test_all_tests_passed_failed_queue_entry(self):
        self._afe_job.hostqueueentry_set.update(complete=True, status='Failed')
        self.assertEqual(False, self._planner_job.active())

        self.assertEqual(False, self._planner_job.all_tests_passed())


    def _setup_test_all_tests_passed(self, status):
        self._afe_job.hostqueueentry_set.update(complete=True,
                                                status='Completed')
        tko_test = tko_models.Test.objects.create(job=self._tko_job,
                                                  status=status,
                                                  kernel=self._tko_kernel,
                                                  machine=self._tko_machine)
        self.assertEqual(False, self._planner_job.active())


    def test_all_tests_passed_success(self):
        self._setup_test_all_tests_passed(self._good_status)
        self.assertEqual(True, self._planner_job.all_tests_passed())


    def test_all_tests_passed_failure(self):
        self._setup_test_all_tests_passed(self._fail_status)
        self.assertEqual(False, self._planner_job.all_tests_passed())


if __name__ == '__main__':
    unittest.main()
