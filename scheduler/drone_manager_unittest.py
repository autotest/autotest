#!/usr/bin/python

import unittest
import common
from autotest_lib.scheduler import drone_manager, drones

class MockDrone(drones._AbstractDrone):
    def __init__(self, name, active_processes, max_processes):
        super(MockDrone, self).__init__()
        self.name = name
        self.active_processes = active_processes
        self.max_processes = max_processes


class DroneManager(unittest.TestCase):
    def setUp(self):
        self.manager = drone_manager.DroneManager()


    def _test_choose_drone_for_execution_helper(self, processes_info_list,
                                                requested_processes):
        for index, process_info in enumerate(processes_info_list):
            active_processes, max_processes = process_info
            self.manager._enqueue_drone(MockDrone(index, active_processes,
                                                  max_processes))

        return self.manager._choose_drone_for_execution(requested_processes)


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


if __name__ == '__main__':
    unittest.main()
