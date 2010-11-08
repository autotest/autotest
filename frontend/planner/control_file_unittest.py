#!/usr/bin/python

import unittest, base64
import common
from autotest_lib.frontend.planner import control_file
from autotest_lib.client.common_lib.test_utils import mock


class ControlFileUnittest(unittest.TestCase):
    def setUp(self):
        self.god = mock.mock_god()


    def tearDown(self):
        self.god.unstub_all()


    def _test_wrap_control_file_helper(self):
        self.verify_params = object()
        self.control = 'control'
        self.verify_segment = '|verify_segment|'
        prepared_verify_args = 'prepared_verify_args'

        self.god.stub_function(control_file, 'prepare_args')
        self.god.stub_function(control_file, 'apply_string_arguments')
        control_file.prepare_args.expect_call(
                self.verify_params).and_return(prepared_verify_args)
        control_file.apply_string_arguments.expect_call(
                control_file.VERIFY_TEST_SEGMENT,
                verify_args=prepared_verify_args).and_return(
                        self.verify_segment)


    def test_wrap_control_file_client(self):
        self._test_wrap_control_file_helper()
        control_base64 = 'control_base64'
        control_segment = '|control_segment|'

        self.god.stub_function(base64, 'encodestring')
        base64.encodestring.expect_call(self.control).and_return(control_base64)
        control_file.apply_string_arguments.expect_call(
                control_file.CLIENT_SEGMENT, control_base64=control_base64,
                control_comment=mock.is_string_comparator()).and_return(
                        control_segment)

        result = control_file.wrap_control_file(control_file=self.control,
                                       is_server=False,
                                       skip_verify=False,
                                       verify_params=self.verify_params)

        self.assertEqual(result, self.verify_segment + control_segment)
        self.god.check_playback()


    def test_wrap_control_file_server(self):
        self._test_wrap_control_file_helper()
        control_segment = '|control_segment|'

        control_file.apply_string_arguments.expect_call(
                control_file.SERVER_SEGMENT,
                control_raw=self.control).and_return(control_segment)

        result = control_file.wrap_control_file(control_file=self.control,
                                       is_server=True,
                                       skip_verify=False,
                                       verify_params=self.verify_params)

        self.assertEqual(result, self.verify_segment + control_segment)
        self.god.check_playback()


if __name__ == '__main__':
    unittest.main()
