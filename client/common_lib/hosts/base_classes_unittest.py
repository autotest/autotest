#!/usr/bin/python

import unittest
import common

from autotest_lib.client.common_lib import error, utils
from autotest_lib.client.common_lib.test_utils import mock
from autotest_lib.client.common_lib.hosts import base_classes


class test_host_class(unittest.TestCase):
    def setUp(self):
        self.god = mock.mock_god()


    def tearDown(self):
        self.god.unstub_all()


    def test_run_output_notimplemented(self):
        host = base_classes.Host()
        self.assertRaises(NotImplementedError, host.run_output, "fake command")


    def test_check_diskspace(self):
        self.god.stub_function(base_classes.Host, 'run')
        host = base_classes.Host()
        host.hostname = 'unittest-host'
        test_df_tail = ('/dev/sda1                    1061       939'
                        '       123      89% /')
        fake_cmd_status = utils.CmdResult(exit_status=0, stdout=test_df_tail)
        host.run.expect_call('df -PB 1000000 /foo | tail -1').and_return(
                fake_cmd_status)
        self.assertRaises(error.AutoservDiskFullHostError,
                          host.check_diskspace, '/foo', 0.2)
        host.run.expect_call('df -PB 1000000 /foo | tail -1').and_return(
                fake_cmd_status)
        host.check_diskspace('/foo', 0.1)
        self.god.check_playback()


if __name__ == "__main__":
    unittest.main()
