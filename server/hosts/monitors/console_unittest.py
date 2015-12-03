#!/usr/bin/python

"""Tests for console.py"""

import StringIO
import os
import shutil
import signal
import tempfile
import unittest

try:
    import autotest.common as common  # pylint: disable=W0611
except ImportError:
    import common  # pylint: disable=W0611

from autotest.client.shared.test_utils import mock
from autotest.server.hosts.monitors import console


class console_test(unittest.TestCase):

    def setUp(self):
        self.god = mock.mock_god()
        self.tempdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tempdir)

    def test_open_logfile(self):
        path = os.path.join(self.tempdir, 'its-log-log')
        fun_log = console._open_logfile(path)
        fun_log.write("it's big it's heavy it's wood.\n")
        fun_log.close()

        # Open it again to ensure the original gets renamed.
        fun_log = console._open_logfile(path)
        fun_log.write("it's better than bad, it's good!\n")
        fun_log.close()

        log_file_list = os.listdir(self.tempdir)
        self.assertEqual(2, len(log_file_list))
        for name in log_file_list:
            self.assertTrue(name.startswith('its-log-log.'),
                            'unexpected name %s' % name)
            self.assertTrue(name.endswith('.gz'), 'unexpected name %s' % name)

    def test_logfile_close_signal_handler(self):
        self.god.stub_function(os, 'exit')
        os.exit.expect_call(1)
        logfile = StringIO.StringIO()
        console._set_logfile_close_signal_handler(logfile)
        try:
            self.assertFalse(logfile.closed)
            os.kill(os.getpid(), signal.SIGTERM)
        finally:
            console._unset_signal_handler()
        self.god.check_playback()
        self.assertTrue(logfile.closed)


if __name__ == '__main__':
    unittest.main()
