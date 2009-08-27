#!/usr/bin/python2.4

import cStringIO, logging, os, sys, unittest

# direct imports; autotest_lib has not been setup while testing this.
from common_lib.test_utils import mock
import setup_modules


class LoggingErrorStderrTests(unittest.TestCase):
    def setUp(self):
        autotest_dir = os.path.abspath(os.path.join(setup_modules.dirname,
                                                    '..'))
        setup_modules.setup(autotest_dir, root_module_name='autotest_lib')
        self.god = mock.mock_god()
        self.test_stderr = cStringIO.StringIO()
        self.god.stub_with(sys, 'stderr', self.test_stderr)
        self.old_root_logging_level = logging.root.level
        logging.basicConfig(level=logging.ERROR)
        # _autotest_logging_handle_error unsets this after being called once.
        logging.raiseExceptions = 1


    def tearDown(self):
        self.god.unstub_all()
        # Undo the setUp logging.basicConfig call.
        logging.basicConfig(level=self.old_root_logging_level)


    def assert_autotest_logging_handle_error_called(self):
        self.stderr_str = self.test_stderr.getvalue()
        self.assertTrue('Exception occurred formatting' in self.stderr_str,
                        repr(self.stderr_str))


    def test_autotest_logging_handle_error(self):
        record = logging.LogRecord(
                'test', logging.DEBUG, __file__, 0, 'MESSAGE', 'ARGS', None)
        try:
            raise RuntimeError('Exception context needed for the test.')
        except RuntimeError:
            setup_modules._autotest_logging_handle_error(logging.Handler(),
                                                         record)
        else:
            self.fail()
        self.assert_autotest_logging_handle_error_called()
        stderr_repr = repr(self.stderr_str)
        self.assertTrue(('MESSAGE' in self.stderr_str), stderr_repr)
        self.assertTrue(('ARGS' in self.stderr_str), stderr_repr)
        self.assertTrue(('Exception' in self.stderr_str), stderr_repr)
        self.assertTrue(('setup_modules_unittest.py' in self.stderr_str),
                        stderr_repr)
        self.assertTrue(('disabled.\n' in self.stderr_str), stderr_repr)
        # Make sure this was turned off by our handle_error.
        self.assertFalse(logging.raiseExceptions)


    def test_logging_monkey_patch_wrong_number_of_args(self):
        logging.error('logging unittest %d %s', 32)
        self.assert_autotest_logging_handle_error_called()
        self.assertTrue('logging unittest' in self.stderr_str,
                        repr(self.stderr_str))


    def test_logging_monkey_patch_wrong_type_of_arg(self):
        logging.error('logging unittest %d', 'eighteen')
        self.assert_autotest_logging_handle_error_called()
        self.assertTrue('logging unittest' in self.stderr_str,
                        repr(self.stderr_str))


    def test_logging_no_error(self):
        logging.error('logging unittest.  %s %s', 'meep', 'meep!')
        self.assertEqual('', self.test_stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
