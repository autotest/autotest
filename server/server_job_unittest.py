#!/usr/bin/python

import unittest

try:
    import autotest.common as common  # pylint: disable=W0611
except ImportError:
    import common  # pylint: disable=W0611

from autotest.server import server_job
from autotest.client.shared import base_job_unittest
from autotest.client.shared.test_utils import mock


class test_find_base_directories(
        unittest.TestCase,
        base_job_unittest.test_find_base_directories.generic_tests):

    def setUp(self):
        self.job = server_job.server_job.__new__(server_job.server_job)

    def test_relative_path_layout(self):
        existing_file = server_job.__file__
        server_job.__file__ = '/rootdir/atest/server/server_job.py'
        try:
            autodir, clientdir, serverdir = (
                self.job._find_base_directories())
            self.assertEqual(autodir, '/rootdir/atest')
            self.assertEqual(clientdir, '/rootdir/atest/client')
            self.assertEqual(serverdir, '/rootdir/atest/server')
        finally:
            server_job.__file__ = existing_file


class test_init(base_job_unittest.test_init.generic_tests, unittest.TestCase):
    OPTIONAL_ATTRIBUTES = (
        base_job_unittest.test_init.generic_tests.OPTIONAL_ATTRIBUTES -
        set(['serverdir', 'conmuxdir', 'num_tests_run', 'num_tests_failed',
             'warning_manager', 'warning_loggers']))

    def setUp(self):
        self.god = mock.mock_god()
        self.job = server_job.base_server_job.__new__(
            server_job.base_server_job)
        self.job._job_directory = base_job_unittest.stub_job_directory

    def call_init(self):
        # TODO(jadmanski): refactor more of the __init__ code to not need to
        # stub out countless random APIs
        self.god.stub_with(server_job.os, 'mkdir', lambda p: None)

        class manager:
            pass

        self.god.stub_with(server_job.logging_manager, 'get_logging_manager',
                           lambda *a, **k: manager())

        class sysi:

            @staticmethod
            def log_per_reboot_data():
                return None

        self.god.stub_with(server_job.sysinfo, 'sysinfo', lambda r: sysi())

        self.job.__init__('/control', (), None, 'job_label',
                          'auser', ['mach1', 'mach2'])
        self.god.unstub_all()


class WarningManagerTest(unittest.TestCase):

    def test_never_disabled(self):
        manager = server_job.warning_manager()
        self.assertEqual(manager.is_valid(10, "MSGTYPE"), True)

    def test_only_enabled(self):
        manager = server_job.warning_manager()
        manager.enable_warnings("MSGTYPE", lambda: 10)
        self.assertEqual(manager.is_valid(20, "MSGTYPE"), True)

    def test_disabled_once(self):
        manager = server_job.warning_manager()
        manager.disable_warnings("MSGTYPE", lambda: 10)
        self.assertEqual(manager.is_valid(5, "MSGTYPE"), True)
        self.assertEqual(manager.is_valid(15, "MSGTYPE"), False)

    def test_disable_and_enabled(self):
        manager = server_job.warning_manager()
        manager.disable_warnings("MSGTYPE", lambda: 10)
        manager.enable_warnings("MSGTYPE", lambda: 20)
        self.assertEqual(manager.is_valid(15, "MSGTYPE"), False)
        self.assertEqual(manager.is_valid(25, "MSGTYPE"), True)

    def test_disabled_changes_is_valid(self):
        manager = server_job.warning_manager()
        self.assertEqual(manager.is_valid(15, "MSGTYPE"), True)
        manager.disable_warnings("MSGTYPE", lambda: 10)
        self.assertEqual(manager.is_valid(15, "MSGTYPE"), False)

    def test_multiple_disabled_calls(self):
        manager = server_job.warning_manager()
        manager.disable_warnings("MSGTYPE", lambda: 10)
        manager.disable_warnings("MSGTYPE", lambda: 20)
        manager.enable_warnings("MSGTYPE", lambda: 30)
        self.assertEqual(manager.is_valid(15, "MSGTYPE"), False)
        self.assertEqual(manager.is_valid(25, "MSGTYPE"), False)
        self.assertEqual(manager.is_valid(35, "MSGTYPE"), True)

    def test_multiple_types(self):
        manager = server_job.warning_manager()
        manager.disable_warnings("MSGTYPE1", lambda: 10)
        manager.disable_warnings("MSGTYPE2", lambda: 20)
        manager.enable_warnings("MSGTYPE2", lambda: 30)
        self.assertEqual(manager.is_valid(15, "MSGTYPE1"), False)
        self.assertEqual(manager.is_valid(15, "MSGTYPE2"), True)
        self.assertEqual(manager.is_valid(25, "MSGTYPE1"), False)
        self.assertEqual(manager.is_valid(25, "MSGTYPE2"), False)
        self.assertEqual(manager.is_valid(35, "MSGTYPE1"), False)
        self.assertEqual(manager.is_valid(35, "MSGTYPE2"), True)


if __name__ == "__main__":
    unittest.main()
