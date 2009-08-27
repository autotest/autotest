#!/usr/bin/python
# Copyright 2009 Google Inc. Released under the GPL v2

import unittest

import common
from autotest_lib.mirror import trigger
from autotest_lib.client.common_lib.test_utils import mock


class map_action_unittest(unittest.TestCase):
    def setUp(self):
        self.god = mock.mock_god()


    def tearDown(self):
        pass


    def test_machine_info_api(self):
        controls = object()
        configs = object()

        info = trigger.map_action.machine_info(controls, configs)
        self.assertEquals(controls, info.control_files)
        self.assertEquals(configs, info.kernel_configs)


    def test_job_grouping(self):
        control_map = {
            'mach1': trigger.map_action.machine_info(
                    ('control1', 'control2'), {'2.6.20': 'config1'}),
            'mach2': trigger.map_action.machine_info(
                    ('control3',), {'2.6.10': 'config2', '2.6.20': 'config1'}),
            'mach3': trigger.map_action.machine_info(
                    ('control2', 'control3'), {'2.6.20': 'config1'}),
            }
        action = trigger.map_action(control_map, 'jobname %s')

        self.god.stub_function(action, '_generate_control')
        self.god.stub_function(action, '_schedule_job')

        (action._generate_control.expect_call('control2', '2.6.21', 'config1')
                .and_return('control contents2'))
        action._schedule_job.expect_call('jobname 2.6.21', 'control contents2',
                                         ['mach1', 'mach3'], False)

        (action._generate_control.expect_call('control3', '2.6.21', 'config1')
                .and_return('control contents3'))
        action._schedule_job.expect_call('jobname 2.6.21', 'control contents3',
                                         ['mach2', 'mach3'], False)

        (action._generate_control.expect_call('control1', '2.6.21', 'config1')
                .and_return('control contents1'))
        action._schedule_job.expect_call('jobname 2.6.21', 'control contents1',
                                         ['mach1'], False)

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


if __name__ == "__main__":
    unittest.main()
