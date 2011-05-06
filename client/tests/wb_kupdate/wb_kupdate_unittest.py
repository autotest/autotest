#!/usr/bin/python

import common
import datetime
import logging
import os
import time
import unittest
from autotest_lib.client.bin import test
from autotest_lib.client.bin import utils
from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib.test_utils import mock
from autotest_lib.client.tests.wb_kupdate import wb_kupdate

class WbKupdateUnitTest(unittest.TestCase):
    def setUp(self):
        """Set up all required variables for the Unittest.
        """
        self._logger = logging.getLogger()
        self._wbkupdate_obj = WbKupdateSubclass()
        self._god = mock.mock_god()

    def test_needs_more_time(self):
        """Tests the _needs_more_time method.
        """
        self._logger.info('Testing the "_needs_more_time" method.')

        # Obvious failure - since start_time < start_time + 1.
        self.assertTrue(self._wbkupdate_obj._needs_more_time(
                start_time=datetime.datetime.now(),
                duration=1))

        # Check if 1 minute has elapsed since start_time.
        self.assertFalse(self._wbkupdate_obj._needs_more_time(
                start_time=datetime.datetime.now(),
                duration=1,
                _now=datetime.datetime.now() + datetime.timedelta(seconds=60)))

    def test_wait_until_data_flushed_pass(self):
        """Tests the _wait_until_data_flushed method.

        This tests the "success" code path.
        """
        self._logger.info('Testing the "_wait_until_data_flushed" method - '
                          'Success code path.')

        # Creating stubs for required methods.
        self._god.stub_function(self._wbkupdate_obj,
                                "_get_disk_usage")

        # Setting default return values for stub functions.
        # Setting the initial size of the file.
        self._wbkupdate_obj._get_disk_usage.expect_call('').and_return(10)
        # Returning the same file size - forcing code path to enter loop.
        self._wbkupdate_obj._get_disk_usage.expect_call('').and_return(10)
        # Returning a greater file size - exiting the while loop.
        self._wbkupdate_obj._get_disk_usage.expect_call('').and_return(11)

        # Call the method.
        self._wbkupdate_obj._wait_until_data_flushed(datetime.datetime.now(),
                                                     1)

        # Ensure all stubbed methods called.
        self._god.check_playback()


    def test_wait_until_data_flushed_fail(self):
        """Tests the _wait_until_data_flushed method.

        This tests the "failure" code path.
        """
        self._logger.info('Testing the "_wait_until_data_flushed" method - '
                          'Failure code path.')
        # Creating stubs for required methods.
        self._god.stub_function(self._wbkupdate_obj,
                                "_get_disk_usage")

        # Setting default return values for stub functions.
        # Setting the initial size of the file.
        self._wbkupdate_obj._get_disk_usage.expect_call('').and_return(10)
        # Returning the same file size - forcing code path to enter loop.
        self._wbkupdate_obj._get_disk_usage.expect_call('').and_return(10)

        # Call the method.
        self.assertRaises(error.TestError,
                          self._wbkupdate_obj._wait_until_data_flushed,
                          start_time=datetime.datetime.now(),
                          max_wait_time=0)

        # Ensure all stubbed methods called.
        self._god.check_playback()


class WbKupdateSubclass(wb_kupdate.wb_kupdate):
    """Sub-classing the wb_kupdate class.
    """
    def __init__(self):
        """Empty constructor.
        """
        # Create all test defaults.
        self.initialize()


if __name__ == '__main__':
    unittest.main()
