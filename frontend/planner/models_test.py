#!/usr/bin/python

import unittest
import common
from autotest_lib.frontend import setup_django_environment
from autotest_lib.frontend.afe import frontend_test_utils, rpc_utils
from autotest_lib.frontend.planner import models


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


if __name__ == '__main__':
    unittest.main()
