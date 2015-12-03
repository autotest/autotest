#!/usr/bin/python

"""Tests for autotest.scheduler.drones."""

import cPickle

try:
    import autotest.common as common  # pylint: disable=W0611
except ImportError:
    import common  # pylint: disable=W0611

from autotest.client.shared import utils
from autotest.client.shared.test_utils import mock, unittest
from autotest.scheduler import drones
from autotest.server.hosts import ssh_host


class RemoteDroneTest(unittest.TestCase):

    def setUp(self):
        self.god = mock.mock_god()
        self._mock_host = self.god.create_mock_class(ssh_host.SSHHost,
                                                     'mock SSHHost')
        self.god.stub_function(drones.drone_utility, 'create_host')

    def tearDown(self):
        self.god.unstub_all()

    def test_unreachable(self):
        drones.drone_utility.create_host.expect_call('fakehost').and_return(
            self._mock_host)
        self._mock_host.is_up.expect_call().and_return(False)
        self.assertRaises(drones.DroneUnreachable,
                          drones._RemoteDrone, 'fakehost')

    def test_execute_calls_impl(self):
        self.god.stub_with(drones._RemoteDrone, '_drone_utility_path',
                           'mock-drone-utility-path')
        drones.drone_utility.create_host.expect_call('fakehost').and_return(
            self._mock_host)
        self._mock_host.is_up.expect_call().and_return(True)
        mock_calls = ('foo',)
        mock_result = utils.CmdResult(stdout=cPickle.dumps('mock return'))
        self._mock_host.run.expect_call(
            'python mock-drone-utility-path',
            stdin=cPickle.dumps(mock_calls), stdout_tee=None,
            connect_timeout=mock.is_instance_comparator(int)).and_return(
            mock_result)

        drone = drones._RemoteDrone('fakehost')
        self.assertEqual('mock return', drone._execute_calls_impl(mock_calls))
        self.god.check_playback()


if __name__ == '__main__':
    unittest.main()
