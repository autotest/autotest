#!/usr/bin/python

import unittest
import common
from autotest_lib.frontend import setup_django_environment
from autotest_lib.frontend.afe import frontend_test_utils, rpc_utils
from autotest_lib.frontend.planner import models, model_attributes


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


if __name__ == '__main__':
    unittest.main()
