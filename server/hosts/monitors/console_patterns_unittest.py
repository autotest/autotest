#!/usr/bin/python

try:
    import autotest.common as common  # pylint: disable=W0611
except ImportError:
    import common  # pylint: disable=W0611
import cStringIO
import os
import unittest

from autotest.server.hosts.monitors import monitors_util


class _MockWarnFile(object):

    def __init__(self):
        self.warnings = []

    def write(self, data):
        if data == '\n':
            return
        timestamp, type, message = data.split('\t')
        self.warnings.append((type, message))


class ConsolePatternsTestCase(unittest.TestCase):

    def setUp(self):
        self._warnfile = _MockWarnFile()
        patterns_path = os.path.join(os.path.dirname(__file__),
                                     'console_patterns')
        self._alert_hooks = monitors_util.build_alert_hooks_from_path(
            patterns_path, self._warnfile)
        self._logfile = cStringIO.StringIO()

    def _process_line(self, line):
        input_file = cStringIO.StringIO(line + '\n')
        monitors_util.process_input(input_file, self._logfile,
                                    alert_hooks=self._alert_hooks)

    def _assert_warning_fired(self, type, message):
        key = (type, message)
        self.assert_(key in self._warnfile.warnings,
                     'Warning %s not found in: %s' % (key,
                                                      self._warnfile.warnings))

    def _assert_no_warnings_fired(self):
        self.assertEquals(self._warnfile.warnings, [])


class ConsolePatternsTest(ConsolePatternsTestCase):

    def test_oops(self):
        self._process_line('<0>Oops: 0002 [1] SMP ')
        self._assert_warning_fired('BUG', "machine Oops'd (: 0002 [1] SMP)")


if __name__ == '__main__':
    unittest.main()
