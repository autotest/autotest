#!/usr/bin/python

import unittest
import common
from autotest_lib.frontend import setup_django_environment
from autotest_lib.frontend.planner import planner_test_utils
from autotest_lib.frontend.afe import model_logic, models as afe_models
from autotest_lib.frontend.afe import rpc_interface as afe_rpc_interface
from autotest_lib.frontend.planner import models, rpc_utils
from autotest_lib.client.common_lib import utils


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


if __name__ == '__main__':
    unittest.main()
