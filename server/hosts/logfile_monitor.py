import logging
import os
import subprocess
import sys
import threading
import time
import traceback

from autotest.client.shared import utils
from autotest.server.hosts import abstract_ssh, monitors

MONITORDIR = monitors.__path__[0]
SUPPORTED_PYTHON_VERS = ('2.4', '2.5', '2.6', '2.7')
DEFAULT_PYTHON = '/usr/bin/python'


class Error(Exception):
    pass


class InvalidPatternsPathError(Error):

    """An invalid patterns_path was specified."""


class InvalidConfigurationError(Error):

    """An invalid configuration was specified."""


class FollowFilesLaunchError(Error):

    """Error occurred launching followfiles remotely."""


def list_remote_pythons(host):
    """List out installed pythons on host."""
    result = host.run('ls /usr/bin/python[0-9]*')
    return result.stdout.splitlines()


def select_supported_python(installed_pythons):
    """Select a supported python from a list"""
    for python in installed_pythons:
        if python[-3:] in SUPPORTED_PYTHON_VERS:
            return python


def copy_monitordir(host):
    """Copy over monitordir to a tmpdir on the remote host."""
    tmp_dir = host.get_tmp_dir()
    host.send_file(MONITORDIR, tmp_dir)
    return os.path.join(tmp_dir, 'monitors')


def launch_remote_followfiles(host, lastlines_dirpath, follow_paths):
    """Launch followfiles.py remotely on follow_paths."""
    logging.info('Launching followfiles on target: %s, %s, %s',
                 host.hostname, lastlines_dirpath, str(follow_paths))

    # First make sure a supported Python is on host
    installed_pythons = list_remote_pythons(host)
    supported_python = select_supported_python(installed_pythons)
    if not supported_python:
        if DEFAULT_PYTHON in installed_pythons:
            logging.info('No versioned Python binary found, '
                         'defaulting to: %s', DEFAULT_PYTHON)
            supported_python = DEFAULT_PYTHON
        else:
            raise FollowFilesLaunchError('No supported Python on host.')

    remote_monitordir = copy_monitordir(host)
    remote_script_path = os.path.join(remote_monitordir, 'followfiles.py')

    followfiles_cmd = '%s %s --lastlines_dirpath=%s %s' % (
        supported_python, remote_script_path,
        lastlines_dirpath, ' '.join(follow_paths))

    remote_ff_proc = subprocess.Popen(host._make_ssh_cmd(followfiles_cmd),
                                      stdin=open(os.devnull, 'r'),
                                      stdout=subprocess.PIPE, shell=True)

    def wait_for_crash():
        """
        Warning: this is not threadsafe due to the call to
        host.job.record()
        """
        # Give it enough time to crash if it's going to (it shouldn't).
        time.sleep(5)
        doa = remote_ff_proc.poll()
        if doa:
            # We're hosed, there is no point in proceeding.
            logging.fatal('Failed to launch followfiles on target,'
                          ' aborting logfile monitoring: %s', host.hostname)
            if host.job:
                # Put a warning in the status.log
                host.job.record(
                    'WARN', None, 'logfile.monitor',
                    'followfiles launch failed')
    crash_waiter = threading.Thread(target=wait_for_crash)
    crash_waiter.start()

    return remote_ff_proc


def resolve_patterns_path(patterns_path):
    """Resolve patterns_path to existing absolute local path or raise.

    As a convenience we allow users to specify a non-absolute patterns_path.
    However these need to be resolved before allowing them to be passed down
    to console.py.

    For now we expect non-absolute ones to be in self.monitordir.
    """
    if os.path.isabs(patterns_path):
        if os.path.exists(patterns_path):
            return patterns_path
        else:
            raise InvalidPatternsPathError('Absolute path does not exist.')
    else:
        patterns_path = os.path.join(MONITORDIR, patterns_path)
        if os.path.exists(patterns_path):
            return patterns_path
        else:
            raise InvalidPatternsPathError('Relative path does not exist.')


def launch_local_console(
        input_stream, console_log_path, pattern_paths=None):
    """Launch console.py locally.

    This will process the output from followfiles and
    fire warning messages per configuration in pattern_paths.
    """
    r, w = os.pipe()
    local_script_path = os.path.join(MONITORDIR, 'console.py')
    console_cmd = [sys.executable, local_script_path]
    if pattern_paths:
        console_cmd.append('--pattern_paths=%s' % ','.join(pattern_paths))

    console_cmd += [console_log_path, str(w)]

    # Setup warning stream before we actually launch
    warning_stream = os.fdopen(r, 'r', 0)

    devnull_w = open(os.devnull, 'w')
    # Launch console.py locally
    console_proc = subprocess.Popen(
        console_cmd, stdin=input_stream,
        stdout=devnull_w, stderr=devnull_w)
    os.close(w)
    return console_proc, warning_stream


def _log_and_ignore_exceptions(f):
    """Decorator: automatically log exception during a method call.
    """

    def wrapped(self, *args, **dargs):
        try:
            return f(self, *args, **dargs)
        except Exception, e:
            print("LogfileMonitor.%s failed with exception %s" % (f.__name__, e))
            print("Exception ignored:")
            traceback.print_exc(file=sys.stdout)
    wrapped.__name__ = f.__name__
    wrapped.__doc__ = f.__doc__
    wrapped.__dict__.update(f.__dict__)
    return wrapped


class LogfileMonitorMixin(abstract_ssh.AbstractSSHHost):

    """This can monitor one or more remote files using tail.

    This class and its counterpart script, monitors/followfiles.py,
    add most functionality one would need to launch and monitor
    remote tail processes on self.hostname.

    This can be used by subclassing normally or by calling
    NewLogfileMonitorMixin (below)

    It is configured via two class attributes:
        follow_paths: Remote paths to monitor
        pattern_paths: Local paths to alert pattern definition files.
    """
    follow_paths = ()
    pattern_paths = ()

    def _initialize(self, console_log=None, *args, **dargs):
        super(LogfileMonitorMixin, self)._initialize(*args, **dargs)

        self._lastlines_dirpath = None
        self._console_proc = None
        self._console_log = console_log or 'logfile_monitor.log'

    def reboot_followup(self, *args, **dargs):
        super(LogfileMonitorMixin, self).reboot_followup(*args, **dargs)
        self.__stop_loggers()
        self.__start_loggers()

    def start_loggers(self):
        super(LogfileMonitorMixin, self).start_loggers()
        self.__start_loggers()

    def remote_path_exists(self, remote_path):
        """Return True if remote_path exists, False otherwise."""
        return not self.run(
            'ls %s' % remote_path, ignore_status=True).exit_status

    def check_remote_paths(self, remote_paths):
        """Return list of remote_paths that currently exist."""
        return [
            path for path in remote_paths if self.remote_path_exists(path)]

    @_log_and_ignore_exceptions
    def __start_loggers(self):
        """Start multifile monitoring logger.

        Launch monitors/followfiles.py on the target and hook its output
        to monitors/console.py locally.
        """
        # Check if follow_paths exist, in the case that one doesn't
        # emit a warning and proceed.
        follow_paths_set = set(self.follow_paths)
        existing = self.check_remote_paths(follow_paths_set)
        missing = follow_paths_set.difference(existing)
        if missing:
            # Log warning that we are missing expected remote paths.
            logging.warn('Target %s is missing expected remote paths: %s',
                         self.hostname, ', '.join(missing))

        # If none of them exist just return (for now).
        if not existing:
            return

        # Create a new lastlines_dirpath on the remote host if not already set.
        if not self._lastlines_dirpath:
            self._lastlines_dirpath = self.get_tmp_dir(parent='/var/tmp')

        # Launch followfiles on target
        self._followfiles_proc = launch_remote_followfiles(
            self, self._lastlines_dirpath, existing)

        # Ensure we have sane pattern_paths before launching console.py
        sane_pattern_paths = []
        for patterns_path in set(self.pattern_paths):
            try:
                patterns_path = resolve_patterns_path(patterns_path)
            except InvalidPatternsPathError, e:
                logging.warn('Specified patterns_path is invalid: %s, %s',
                             patterns_path, str(e))
            else:
                sane_pattern_paths.append(patterns_path)

        # Launch console.py locally, pass in output stream from followfiles.
        self._console_proc, self._logfile_warning_stream = \
            launch_local_console(
                self._followfiles_proc.stdout, self._console_log,
                sane_pattern_paths)

        if self.job:
            self.job.warning_loggers.add(self._logfile_warning_stream)

    def stop_loggers(self):
        super(LogfileMonitorMixin, self).stop_loggers()
        self.__stop_loggers()

    @_log_and_ignore_exceptions
    def __stop_loggers(self):
        if self._console_proc:
            utils.nuke_subprocess(self._console_proc)
            utils.nuke_subprocess(self._followfiles_proc)
            self._console_proc = self._followfile_proc = None
            if self.job:
                self.job.warning_loggers.discard(self._logfile_warning_stream)
            self._logfile_warning_stream.close()


def NewLogfileMonitorMixin(follow_paths, pattern_paths=None):
    """Create a custom in-memory subclass of LogfileMonitorMixin.

    Args:
      follow_paths: list; Remote paths to tail.
      pattern_paths: list; Local alert pattern definition files.
    """
    if not follow_paths or (pattern_paths and not follow_paths):
        raise InvalidConfigurationError

    return type(
        'LogfileMonitorMixin%d' % id(follow_paths),
        (LogfileMonitorMixin,),
        {'follow_paths': follow_paths,
         'pattern_paths': pattern_paths or ()})
