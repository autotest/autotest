#!/usr/bin/python

"""Tests for drone_utility."""

import os, sys, unittest
from cStringIO import StringIO

import common
from autotest_lib.client.common_lib import global_config
from autotest_lib.client.common_lib.test_utils import mock
from autotest_lib.scheduler import drone_utility


class TestDroneUtility(unittest.TestCase):
    def setUp(self):
        self.drone_utility = drone_utility.DroneUtility()
        self._fake_command = '!faketest!'
        self._fake_proc_info = {'pid': 3, 'pgid': 4, 'ppid': 2,
                                'comm': self._fake_command, 'args': ''}
        self.god = mock.mock_god()
        self.god.stub_function(self.drone_utility, '_get_process_info')


    def tearDown(self):
        self.god.unstub_all()
        global_config.global_config.reset_config_values()


    @staticmethod
    def _set_check_dark_mark(value):
        global_config.global_config.override_config_value(
                'SCHEDULER', 'check_processes_for_dark_mark', repr(value))


    def test_refresh_processes_ignore_dark_mark(self):
        self._set_check_dark_mark(False)
        self.drone_utility._get_process_info.expect_call().and_return(
                [self._fake_proc_info])
        fake_open = lambda path, mode: self.fail('dark mark checked!')
        processes = self.drone_utility._refresh_processes(self._fake_command,
                                                          open=fake_open)
        our_pid = self._fake_proc_info['pid']
        for process in processes:
            if our_pid == process['pid']:
                break
        else:
            self.fail("No %s processes found" % self._fake_command)
        self.god.check_playback()


    def test_refresh_processes_check_dark_mark(self):
        self._set_check_dark_mark(True)
        num_procs = 2
        proc_info_list = num_procs * [self._fake_proc_info]

        self.drone_utility._get_process_info.expect_call().and_return(
                proc_info_list)
        # Test processes that have the mark in their env.
        def _open_mark(path, mode):
            return StringIO('foo=\0%s=\0bar=\0' %
                           drone_utility.DARK_MARK_ENVIRONMENT_VAR)
        processes = self.drone_utility._refresh_processes(self._fake_command,
                                                          open=_open_mark)
        self.assertEqual(num_procs, len(processes))
        self.assertEqual(proc_info_list, processes)

        self.drone_utility._get_process_info.expect_call().and_return(
                proc_info_list)
        # Test processes that do not have the mark in their env
        def _open_nomark(path, mode):
            return StringIO('foo=\0bar=\0')  # No dark mark.
        processes = self.drone_utility._refresh_processes(self._fake_command,
                                                          open=_open_nomark)
        self.assertEqual([], processes)
        self.god.check_playback()


if __name__ == '__main__':
    unittest.main()
