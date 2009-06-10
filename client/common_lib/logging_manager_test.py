#!/usr/bin/python

import logging, os, select, StringIO, subprocess, sys, unittest
import common
from autotest_lib.client.common_lib import logging_manager, logging_config


class PipedStringIO(object):
    """
    Like StringIO, but all I/O passes through a pipe.  This means a
    PipedStringIO is backed by a file descriptor is thus can do things like
    pass down to a subprocess.  However, this means the creating process must
    call read_pipe() (or the classmethod read_all_pipes()) periodically to read
    the pipe, and must call close() (or the classmethod cleanup()) to close the
    pipe.
    """
    _instances = set()

    def __init__(self):
        self._string_io = StringIO.StringIO()
        self._read_end, self._write_end = os.pipe()
        PipedStringIO._instances.add(self)


    def close(self):
        self._string_io.close()
        os.close(self._read_end)
        os.close(self._write_end)
        PipedStringIO._instances.remove(self)


    def write(self, data):
        os.write(self._write_end, data)


    def flush(self):
        pass


    def fileno(self):
        return self._write_end


    def getvalue(self):
        self.read_pipe()
        return self._string_io.getvalue()


    def read_pipe(self):
        while True:
            read_list, _, _ = select.select([self._read_end], [], [], 0)
            if not read_list:
                return
            self._string_io.write(os.read(self._read_end, 1024))


    @classmethod
    def read_all_pipes(cls):
        for instance in cls._instances:
            instance.read_pipe()


    @classmethod
    def cleanup_all_instances(cls):
        for instance in list(cls._instances):
            instance.close()


LOGGING_FORMAT = '%(levelname)s: %(message)s'

_EXPECTED_STDOUT = """\
print 1
system 1
INFO: logging 1
DEBUG: print 2
DEBUG: system 2
INFO: logging 2
DEBUG: print 6
DEBUG: system 6
INFO: logging 6
print 7
system 7
INFO: logging 7
"""

_EXPECTED_LOG1 = """\
DEBUG: print 3
DEBUG: system 3
INFO: logging 3
DEBUG: print 4
DEBUG: system 4
INFO: logging 4
DEBUG: print 5
DEBUG: system 5
INFO: logging 5
"""

_EXPECTED_LOG2 = """\
DEBUG: print 4
DEBUG: system 4
INFO: logging 4
"""


class DummyLoggingConfig(logging_config.LoggingConfig):
    CONSOLE_FORMATTER = logging.Formatter(LOGGING_FORMAT)

    def __init__(self):
        super(DummyLoggingConfig, self).__init__()
        self.log = PipedStringIO()


    def add_debug_file_handlers(self, log_dir, log_name=None):
        self.logger.addHandler(logging.StreamHandler(self.log))


# this isn't really a unit test since it creates subprocesses and pipes and all
# that. i just use the unittest framework because it's convenient.
class LoggingManagerTest(unittest.TestCase):
    def setUp(self):
        self.stdout = PipedStringIO()
        self._log1 = PipedStringIO()
        self._log2 = PipedStringIO()

        self._real_system_calls = False

        # the LoggingManager will change self.stdout (by design), so keep a
        # copy around
        self._original_stdout = self.stdout

        logging.basicConfig(level=logging.DEBUG, format=LOGGING_FORMAT,
                            stream=self.stdout)

        self._config_object = DummyLoggingConfig()
        logging_manager.LoggingManager.logging_config_object = (
                self._config_object)


    def tearDown(self):
        PipedStringIO.cleanup_all_instances()


    def _say(self, suffix):
        print >>self.stdout, 'print %s' % suffix
        if self._real_system_calls:
            os.system('echo system %s >&%s' % (suffix,
                                               self._original_stdout.fileno()))
        else:
            print >>self.stdout, 'system %s' % suffix
        logging.info('logging %s', suffix)
        PipedStringIO.read_all_pipes()


    def _setup_manager(self, manager_class=logging_manager.LoggingManager):
        def set_stdout(file_object):
            self.stdout = file_object
        manager = manager_class()
        manager.manage_stream(self.stdout, logging.DEBUG, set_stdout)
        return manager


    def _run_test(self, manager_class):
        manager = self._setup_manager(manager_class)

        self._say(1)

        manager.start_logging()
        self._say(2)

        manager.redirect_to_stream(self._log1)
        self._say(3)

        manager.tee_redirect_to_stream(self._log2)
        self._say(4)

        manager.undo_redirect()
        self._say(5)

        manager.undo_redirect()
        self._say(6)

        manager.stop_logging()
        self._say(7)


    def _grab_fd_info(self):
        command = 'ls -l /proc/%s/fd' % os.getpid()
        proc = subprocess.Popen(command.split(), shell=True,
                                stdout=subprocess.PIPE)
        return proc.communicate()[0]


    def _compare_logs(self, log_buffer, expected_text):
        actual_lines = log_buffer.getvalue().splitlines()
        expected_lines = expected_text.splitlines()
        if self._real_system_calls:
            # because of the many interacting processes, we can't ensure perfect
            # interleaving.  so compare sets of lines rather than ordered lines.
            actual_lines = set(actual_lines)
            expected_lines = set(expected_lines)
        self.assertEquals(actual_lines, expected_lines)


    def _check_results(self):
        # ensure our stdout was restored
        self.assertEquals(self.stdout, self._original_stdout)

        if self._real_system_calls:
            # ensure FDs were left in their original state
            self.assertEquals(self._grab_fd_info(), self._fd_info)

        self._compare_logs(self.stdout, _EXPECTED_STDOUT)
        self._compare_logs(self._log1, _EXPECTED_LOG1)
        self._compare_logs(self._log2, _EXPECTED_LOG2)


    def test_logging_manager(self):
        self._run_test(logging_manager.LoggingManager)
        self._check_results()


    def test_fd_redirection_logging_manager(self):
        self._real_system_calls = True
        self._fd_info = self._grab_fd_info()
        self._run_test(logging_manager.FdRedirectionLoggingManager)
        self._check_results()


    def test_tee_redirect_debug_dir(self):
        manager = self._setup_manager()
        manager.start_logging()

        manager.tee_redirect_debug_dir('/fake/dir', tag='mytag')
        print >>self.stdout, 'hello'

        manager.undo_redirect()
        print >>self.stdout, 'goodbye'

        manager.stop_logging()

        self._compare_logs(self.stdout,
                           'DEBUG: mytag : hello\nDEBUG: goodbye')
        self._compare_logs(self._config_object.log, 'hello\n')


if __name__ == '__main__':
    unittest.main()
