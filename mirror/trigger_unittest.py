#!/usr/bin/python
# Copyright 2009 Google Inc. Released under the GPL v2

import unittest

try:
    import autotest.common as common  # pylint: disable=W0611
except ImportError:
    import common  # pylint: disable=W0611
from autotest.mirror import trigger
from autotest.client.shared.test_utils import mock


class map_action_unittest(unittest.TestCase):

    def setUp(self):
        self.god = mock.mock_god()

    def tearDown(self):
        pass

    def test_machine_info_api(self):
        tests = object()
        configs = object()

        info = trigger.map_action.machine_info(tests, configs)
        self.assertEquals(tests, info.tests)
        self.assertEquals(configs, info.kernel_configs)

    @staticmethod
    def _make_control_dict(contents, is_server=False, synch_count=1,
                           dependencies=()):
        class ControlFile(object):

            def __init__(self, contents, is_server, synch_count, dependencies):
                self.control_file = contents
                self.is_server = is_server
                self.synch_count = synch_count
                self.dependencies = dependencies

        return ControlFile(contents, is_server, synch_count, dependencies)

    def test_job_grouping(self):
        tests_map = {
            'mach1': trigger.map_action.machine_info(
                ('test1', 'test2'), {'2.6.20': 'config1'}),
            'mach2': trigger.map_action.machine_info(
                ('test3',), {'2.6.10': 'config2', '2.6.20': 'config1'}),
            'mach3': trigger.map_action.machine_info(
                ('test2', 'test3'), {'2.6.20': 'config1'}),
        }
        action = trigger.map_action(tests_map, 'jobname %s')
        self.assertTrue(isinstance(action._afe, trigger.frontend.AFE))
        action._afe = self.god.create_mock_class(trigger.frontend.AFE, 'AFE')

        control2 = self._make_control_dict('control contents2')
        (action._afe.generate_control_file.expect_call(
            tests=['test2'],
            kernel=[dict(version='2.6.21', config_file='config1')],
            upload_kernel_config=False)
         .and_return(control2))
        action._afe.create_job.expect_call(
            control2.control_file, 'jobname 2.6.21',
            control_type='Client', hosts=['mach1', 'mach3'])

        control3 = self._make_control_dict('control contents3', is_server=True)
        (action._afe.generate_control_file.expect_call(
            tests=['test3'],
            kernel=[dict(version='2.6.21', config_file='config1')],
            upload_kernel_config=False)
         .and_return(control3))
        action._afe.create_job.expect_call(
            control3.control_file, 'jobname 2.6.21',
            control_type='Server', hosts=['mach2', 'mach3'])

        control1 = self._make_control_dict('control contents1')
        (action._afe.generate_control_file.expect_call(
            tests=['test1'],
            kernel=[dict(version='2.6.21', config_file='config1')],
            upload_kernel_config=False)
         .and_return(control1))
        action._afe.create_job.expect_call(
            control1.control_file, 'jobname 2.6.21',
            control_type='Client', hosts=['mach1'])

        action(['2.6.21'])
        self.god.check_playback()

    def test_kver_cmp(self):
        def check_cmp(ver1, ver2):
            # function to make sure "cmp" invariants are followed
            cmp_func = trigger.map_action._kver_cmp
            if ver1 != ver2:
                self.assertEquals(cmp_func(ver1, ver2), -1)
                self.assertEquals(cmp_func(ver2, ver1), 1)
            else:
                self.assertEquals(cmp_func(ver1, ver2), 0)
                self.assertEquals(cmp_func(ver2, ver1), 0)

        check_cmp('2.6.20', '2.6.20')
        check_cmp('2.6.20', '2.6.21')
        check_cmp('2.6.20', '2.6.21-rc2')
        check_cmp('2.6.20-rc2-git2', '2.6.20-rc2')

    def test_upload_kernel_config(self):
        tests_map = {
            'mach1': trigger.map_action.machine_info(
                ('test1',), {'2.6.20': 'config1'}),
            'mach3': trigger.map_action.machine_info(
                ('test1',), {'2.6.20': 'config1'})
        }

        action = trigger.map_action(tests_map, 'jobname %s',
                                    upload_kernel_config=True)
        self.assertTrue(isinstance(action._afe, trigger.frontend.AFE))
        action._afe = self.god.create_mock_class(trigger.frontend.AFE, 'AFE')

        control = self._make_control_dict('control contents', is_server=True)
        (action._afe.generate_control_file.expect_call(
            tests=['test1'],
            kernel=[dict(version='2.6.21', config_file='config1')],
            upload_kernel_config=True)
         .and_return(control))
        action._afe.create_job.expect_call(
            control.control_file, 'jobname 2.6.21',
            control_type='Server', hosts=['mach1', 'mach3'])

        action(['2.6.21'])
        self.god.check_playback()


if __name__ == "__main__":
    unittest.main()
