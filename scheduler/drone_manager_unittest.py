#!/usr/bin/python

import os
import unittest
try:
    import autotest.common as common  # pylint: disable=W0611
except ImportError:
    import common  # pylint: disable=W0611
from autotest.client.shared.settings import settings
from autotest.client.shared.test_utils import mock
from autotest.scheduler import drone_manager, drones
from autotest.scheduler import scheduler_config


class MockDrone(drones._AbstractDrone):

    def __init__(self, name, active_processes=0, max_processes=10,
                 allowed_users=None):
        super(MockDrone, self).__init__()
        self.name = name
        self.hostname = name
        self.active_processes = active_processes
        self.max_processes = max_processes
        self.allowed_users = allowed_users
        # maps method names list of tuples containing method arguments
        self._recorded_calls = {'queue_call': [],
                                'send_file_to': []}

    def queue_call(self, method, *args, **kwargs):
        self._recorded_calls['queue_call'].append((method, args, kwargs))

    def call(self, method, *args, **kwargs):
        # don't bother differentiating between call() and queue_call()
        return self.queue_call(method, *args, **kwargs)

    def send_file_to(self, drone, source_path, destination_path,
                     can_fail=False):
        self._recorded_calls['send_file_to'].append(
            (drone, source_path, destination_path))

    # method for use by tests
    def _check_for_recorded_call(self, method_name, arguments):
        recorded_arg_list = self._recorded_calls[method_name]
        was_called = arguments in recorded_arg_list
        if not was_called:
            print 'Recorded args:', recorded_arg_list
            print 'Expected:', arguments
        return was_called

    def was_call_queued(self, method, *args, **kwargs):
        return self._check_for_recorded_call('queue_call',
                                             (method, args, kwargs))

    def was_file_sent(self, drone, source_path, destination_path):
        return self._check_for_recorded_call('send_file_to',
                                             (drone, source_path,
                                              destination_path))


class DroneManager(unittest.TestCase):
    _DRONE_INSTALL_DIR = '/drone/install/dir'
    _DRONE_RESULTS_DIR = os.path.join(_DRONE_INSTALL_DIR, 'results')
    _RESULTS_DIR = '/results/dir'
    _SOURCE_PATH = 'source/path'
    _DESTINATION_PATH = 'destination/path'
    _WORKING_DIRECTORY = 'working/directory'
    _USERNAME = 'my_user'

    def setUp(self):
        self.god = mock.mock_god()
        self.god.stub_with(drones, 'AUTOTEST_INSTALL_DIR',
                           self._DRONE_INSTALL_DIR)
        self.manager = drone_manager.DroneManager()
        self.god.stub_with(self.manager, '_results_dir', self._RESULTS_DIR)

        # we don't want this to ever actually get called
        self.god.stub_function(drones, 'get_drone')
        # we don't want the DroneManager to go messing with global config

        def do_nothing():
            pass
        self.god.stub_with(self.manager, 'refresh_drone_configs', do_nothing)

        # set up some dummy drones
        self.mock_drone = MockDrone('mock_drone')
        self.manager._drones[self.mock_drone.name] = self.mock_drone
        self.results_drone = MockDrone('results_drone', 0, 10)
        self.manager._results_drone = self.results_drone

        self.mock_drone_process = drone_manager.Process(self.mock_drone.name, 0)

    def tearDown(self):
        self.god.unstub_all()

    def _test_choose_drone_for_execution_helper(self, processes_info_list,
                                                requested_processes):
        for index, process_info in enumerate(processes_info_list):
            active_processes, max_processes = process_info
            self.manager._enqueue_drone(MockDrone(index, active_processes,
                                                  max_processes))

        return self.manager._choose_drone_for_execution(requested_processes,
                                                        self._USERNAME, None)

    def test_choose_drone_for_execution(self):
        drone = self._test_choose_drone_for_execution_helper([(1, 2), (0, 2)],
                                                             1)
        self.assertEquals(drone.name, 1)

    def test_choose_drone_for_execution_some_full(self):
        drone = self._test_choose_drone_for_execution_helper([(0, 1), (1, 3)],
                                                             2)
        self.assertEquals(drone.name, 1)

    def test_choose_drone_for_execution_all_full(self):
        drone = self._test_choose_drone_for_execution_helper([(2, 1), (3, 2)],
                                                             1)
        self.assertEquals(drone.name, 1)

    def test_choose_drone_for_execution_all_full_same_percentage_capacity(self):
        drone = self._test_choose_drone_for_execution_helper([(5, 3), (10, 6)],
                                                             1)
        self.assertEquals(drone.name, 1)

    def test_user_restrictions(self):
        # this drone is restricted to a different user
        self.manager._enqueue_drone(MockDrone(1, max_processes=10,
                                              allowed_users=['fakeuser']))
        # this drone is allowed but has lower capacity
        self.manager._enqueue_drone(MockDrone(2, max_processes=2,
                                              allowed_users=[self._USERNAME]))

        self.assertEquals(2,
                          self.manager.max_runnable_processes(self._USERNAME,
                                                              None))
        drone = self.manager._choose_drone_for_execution(
            1, username=self._USERNAME, drone_hostnames_allowed=None)
        self.assertEquals(drone.name, 2)

    def test_user_restrictions_with_full_drone(self):
        # this drone is restricted to a different user
        self.manager._enqueue_drone(MockDrone(1, max_processes=10,
                                              allowed_users=['fakeuser']))
        # this drone is allowed but is full
        self.manager._enqueue_drone(MockDrone(2, active_processes=3,
                                              max_processes=2,
                                              allowed_users=[self._USERNAME]))

        self.assertEquals(0,
                          self.manager.max_runnable_processes(self._USERNAME,
                                                              None))
        drone = self.manager._choose_drone_for_execution(
            1, username=self._USERNAME, drone_hostnames_allowed=None)
        self.assertEquals(drone.name, 2)

    def _setup_test_drone_restrictions(self, active_processes=0):
        self.manager._enqueue_drone(MockDrone(
            1, active_processes=active_processes, max_processes=10))
        self.manager._enqueue_drone(MockDrone(
            2, active_processes=active_processes, max_processes=5))
        self.manager._enqueue_drone(MockDrone(
            3, active_processes=active_processes, max_processes=2))

    def test_drone_restrictions_allow_any(self):
        self._setup_test_drone_restrictions()
        self.assertEquals(10,
                          self.manager.max_runnable_processes(self._USERNAME,
                                                              None))
        drone = self.manager._choose_drone_for_execution(
            1, username=self._USERNAME, drone_hostnames_allowed=None)
        self.assertEqual(drone.name, 1)

    def test_drone_restrictions_under_capacity(self):
        self._setup_test_drone_restrictions()
        drone_hostnames_allowed = (2, 3)
        self.assertEquals(
            5, self.manager.max_runnable_processes(self._USERNAME,
                                                   drone_hostnames_allowed))
        drone = self.manager._choose_drone_for_execution(
            1, username=self._USERNAME,
            drone_hostnames_allowed=drone_hostnames_allowed)

        self.assertEqual(drone.name, 2)

    def test_drone_restrictions_over_capacity(self):
        self._setup_test_drone_restrictions(active_processes=6)
        drone_hostnames_allowed = (2, 3)
        self.assertEquals(
            0, self.manager.max_runnable_processes(self._USERNAME,
                                                   drone_hostnames_allowed))
        drone = self.manager._choose_drone_for_execution(
            7, username=self._USERNAME,
            drone_hostnames_allowed=drone_hostnames_allowed)
        self.assertEqual(drone.name, 2)

    def test_drone_restrictions_allow_none(self):
        self._setup_test_drone_restrictions()
        drone_hostnames_allowed = ()
        self.assertEquals(
            0, self.manager.max_runnable_processes(self._USERNAME,
                                                   drone_hostnames_allowed))
        drone = self.manager._choose_drone_for_execution(
            1, username=self._USERNAME,
            drone_hostnames_allowed=drone_hostnames_allowed)
        self.assertEqual(drone, None)

    def test_initialize(self):
        results_hostname = 'results_repo'
        results_install_dir = '/results/install'
        settings.override_value(scheduler_config.CONFIG_SECTION,
                                'results_host_installation_directory',
                                results_install_dir)

        (drones.get_drone.expect_call(self.mock_drone.name)
         .and_return(self.mock_drone))

        results_drone = MockDrone('results_drone')
        self.god.stub_function(results_drone, 'set_autotest_install_dir')
        drones.get_drone.expect_call(results_hostname).and_return(results_drone)
        results_drone.set_autotest_install_dir.expect_call(results_install_dir)

        self.manager.initialize(base_results_dir=self._RESULTS_DIR,
                                drone_hostnames=[self.mock_drone.name],
                                results_repository_hostname=results_hostname)

        self.assert_(self.mock_drone.was_call_queued(
            'initialize', self._DRONE_RESULTS_DIR + '/'))
        self.god.check_playback()

    def test_execute_command(self):
        self.manager._enqueue_drone(self.mock_drone)

        pidfile_name = 'my_pidfile'
        log_file = 'log_file'

        pidfile_id = self.manager.execute_command(
            command=['test', drone_manager.WORKING_DIRECTORY],
            working_directory=self._WORKING_DIRECTORY,
            pidfile_name=pidfile_name,
            num_processes=1,
            log_file=log_file)

        full_working_directory = os.path.join(self._DRONE_RESULTS_DIR,
                                              self._WORKING_DIRECTORY)
        self.assertEquals(pidfile_id.path,
                          os.path.join(full_working_directory, pidfile_name))
        self.assert_(self.mock_drone.was_call_queued(
            'execute_command', ['test', full_working_directory],
            full_working_directory,
            os.path.join(self._DRONE_RESULTS_DIR, log_file), pidfile_name))

    def test_attach_file_to_execution(self):
        self.manager._enqueue_drone(self.mock_drone)

        contents = 'my\ncontents'
        attached_path = self.manager.attach_file_to_execution(
            self._WORKING_DIRECTORY, contents)
        self.manager.execute_command(command=['test'],
                                     working_directory=self._WORKING_DIRECTORY,
                                     pidfile_name='mypidfile',
                                     num_processes=1,
                                     drone_hostnames_allowed=None)

        self.assert_(self.mock_drone.was_call_queued(
            'write_to_file',
            os.path.join(self._DRONE_RESULTS_DIR, attached_path),
            contents))

    def test_copy_results_on_drone(self):
        self.manager.copy_results_on_drone(self.mock_drone_process,
                                           self._SOURCE_PATH,
                                           self._DESTINATION_PATH)
        self.assert_(self.mock_drone.was_call_queued(
            'copy_file_or_directory',
            os.path.join(self._DRONE_RESULTS_DIR, self._SOURCE_PATH),
            os.path.join(self._DRONE_RESULTS_DIR, self._DESTINATION_PATH)))

    def test_copy_to_results_repository(self):
        self.manager.copy_to_results_repository(self.mock_drone_process,
                                                self._SOURCE_PATH)
        self.assert_(self.mock_drone.was_file_sent(
            self.results_drone,
            os.path.join(self._DRONE_RESULTS_DIR, self._SOURCE_PATH),
            os.path.join(self._RESULTS_DIR, self._SOURCE_PATH)))

    def test_write_lines_to_file(self):
        file_path = 'file/path'
        lines = ['line1', 'line2']
        written_data = 'line1\nline2\n'

        # write to results repository
        self.manager.write_lines_to_file(file_path, lines)
        self.assert_(self.results_drone.was_call_queued(
            'write_to_file', os.path.join(self._RESULTS_DIR, file_path),
            written_data))

        # write to a drone
        self.manager.write_lines_to_file(
            file_path, lines, paired_with_process=self.mock_drone_process)
        self.assert_(self.mock_drone.was_call_queued(
            'write_to_file',
            os.path.join(self._DRONE_RESULTS_DIR, file_path), written_data))

    def test_pidfile_expiration(self):
        self.god.stub_with(self.manager, '_get_max_pidfile_refreshes',
                           lambda: 0)
        pidfile_id = self.manager.get_pidfile_id_from('tag', 'name')
        self.manager.register_pidfile(pidfile_id)
        self.manager._drop_old_pidfiles()
        self.manager._drop_old_pidfiles()
        self.assertFalse(self.manager._registered_pidfile_info)


if __name__ == '__main__':
    unittest.main()
