#!/usr/bin/python

import pickle, subprocess, os, shutil, socket, sys, time, signal, getpass
import datetime, traceback, tempfile, itertools, logging
import common
from autotest_lib.client.common_lib import utils, global_config, error
from autotest_lib.server import hosts, subcommand
from autotest_lib.scheduler import email_manager, scheduler_config

# An environment variable we add to the environment to enable us to
# distinguish processes we started from those that were started by
# something else during recovery.  Name credit goes to showard. ;)
DARK_MARK_ENVIRONMENT_VAR = 'AUTOTEST_SCHEDULER_DARK_MARK'

_TEMPORARY_DIRECTORY = 'drone_tmp'
_TRANSFER_FAILED_FILE = '.transfer_failed'


class _MethodCall(object):
    def __init__(self, method, args, kwargs):
        self._method = method
        self._args = args
        self._kwargs = kwargs


    def execute_on(self, drone_utility):
        method = getattr(drone_utility, self._method)
        return method(*self._args, **self._kwargs)


    def __str__(self):
        args = ', '.join(repr(arg) for arg in self._args)
        kwargs = ', '.join('%s=%r' % (key, value) for key, value in
                           self._kwargs.iteritems())
        full_args = ', '.join(item for item in (args, kwargs) if item)
        return '%s(%s)' % (self._method, full_args)


def call(method, *args, **kwargs):
    return _MethodCall(method, args, kwargs)


class DroneUtility(object):
    """
    This class executes actual OS calls on the drone machine.

    All paths going into and out of this class are absolute.
    """
    _WARNING_DURATION = 60

    def __init__(self):
        # Tattoo ourselves so that all of our spawn bears our mark.
        os.putenv(DARK_MARK_ENVIRONMENT_VAR, str(os.getpid()))

        self.warnings = []
        self._subcommands = []


    def initialize(self, results_dir):
        temporary_directory = os.path.join(results_dir, _TEMPORARY_DIRECTORY)
        if os.path.exists(temporary_directory):
            shutil.rmtree(temporary_directory)
        self._ensure_directory_exists(temporary_directory)


    def _warn(self, warning):
        self.warnings.append(warning)


    @staticmethod
    def _check_pid_for_dark_mark(pid, open=open):
        try:
            env_file = open('/proc/%s/environ' % pid, 'rb')
        except EnvironmentError:
            return False
        try:
            env_data = env_file.read()
        finally:
            env_file.close()
        return DARK_MARK_ENVIRONMENT_VAR in env_data


    _PS_ARGS = ('pid', 'pgid', 'ppid', 'comm', 'args')


    @classmethod
    def _get_process_info(cls):
        """
        @returns A generator of dicts with cls._PS_ARGS as keys and
                string values each representing a running process.
        """
        ps_proc = subprocess.Popen(
            ['/bin/ps', 'x', '-o', ','.join(cls._PS_ARGS)],
            stdout=subprocess.PIPE)
        ps_output = ps_proc.communicate()[0]

        # split each line into the columns output by ps
        split_lines = [line.split(None, 4) for line in ps_output.splitlines()]
        return (dict(itertools.izip(cls._PS_ARGS, line_components))
                for line_components in split_lines)


    def _refresh_processes(self, command_name, open=open):
        # The open argument is used for test injection.
        check_mark = global_config.global_config.get_config_value(
            'SCHEDULER', 'check_processes_for_dark_mark', bool, False)
        processes = []
        for info in self._get_process_info():
            if info['comm'] == command_name:
                if (check_mark and not
                        self._check_pid_for_dark_mark(info['pid'], open=open)):
                    self._warn('%(comm)s process pid %(pid)s has no '
                               'dark mark; ignoring.' % info)
                    continue
                processes.append(info)

        return processes


    def _read_pidfiles(self, pidfile_paths):
        pidfiles = {}
        for pidfile_path in pidfile_paths:
            if not os.path.exists(pidfile_path):
                continue
            try:
                file_object = open(pidfile_path, 'r')
                pidfiles[pidfile_path] = file_object.read()
                file_object.close()
            except IOError:
                continue
        return pidfiles


    def refresh(self, pidfile_paths):
        """
        pidfile_paths should be a list of paths to check for pidfiles.

        Returns a dict containing:
        * pidfiles: dict mapping pidfile paths to file contents, for pidfiles
        that exist.
        * autoserv_processes: list of dicts corresponding to running autoserv
        processes.  each dict contain pid, pgid, ppid, comm, and args (see
        "man ps" for details).
        * parse_processes: likewise, for parse processes.
        * pidfiles_second_read: same info as pidfiles, but gathered after the
        processes are scanned.
        """
        results = {
            'pidfiles' : self._read_pidfiles(pidfile_paths),
            'autoserv_processes' : self._refresh_processes('autoserv'),
            'parse_processes' : self._refresh_processes('parse'),
            'pidfiles_second_read' : self._read_pidfiles(pidfile_paths),
        }
        return results


    def _is_process_running(self, process):
        # TODO: enhance this to check the process args
        proc_path = os.path.join('/proc', str(process.pid))
        return os.path.exists(proc_path)


    def kill_process(self, process):
        if self._is_process_running(process):
            os.kill(process.pid, signal.SIGCONT)
            os.kill(process.pid, signal.SIGTERM)


    def _convert_old_host_log(self, log_path):
        """
        For backwards compatibility only.  This can safely be removed in the
        future.

        The scheduler used to create files at results/hosts/<hostname>, and
        append all host logs to that file.  Now, it creates directories at
        results/hosts/<hostname>, and places individual timestamped log files
        into that directory.

        This can be a problem the first time the scheduler runs after upgrading.
        To work around that, we'll look for a file at the path where the
        directory should be, and if we find one, we'll automatically convert it
        to a directory containing the old logfile.
        """
        # move the file out of the way
        temp_dir = tempfile.mkdtemp(suffix='.convert_host_log')
        base_name = os.path.basename(log_path)
        temp_path = os.path.join(temp_dir, base_name)
        os.rename(log_path, temp_path)

        os.mkdir(log_path)

        # and move it into the new directory
        os.rename(temp_path, os.path.join(log_path, 'old_log'))
        os.rmdir(temp_dir)


    def _ensure_directory_exists(self, path):
        if os.path.isdir(path):
            return

        if os.path.exists(path):
            # path exists already, but as a file, not a directory
            if '/hosts/' in path:
                self._convert_old_host_log(path)
                return
            else:
                raise IOError('Path %s exists as a file, not a directory')

        os.makedirs(path)


    def execute_command(self, command, working_directory, log_file,
                        pidfile_name):
        out_file = None
        if log_file:
            self._ensure_directory_exists(os.path.dirname(log_file))
            try:
                out_file = open(log_file, 'a')
                separator = ('*' * 80) + '\n'
                out_file.write('\n' + separator)
                out_file.write("%s> %s\n" % (time.strftime("%X %x"), command))
                out_file.write(separator)
            except (OSError, IOError):
                email_manager.manager.log_stacktrace(
                    'Error opening log file %s' % log_file)

        if not out_file:
            out_file = open('/dev/null', 'w')

        in_devnull = open('/dev/null', 'r')

        self._ensure_directory_exists(working_directory)
        pidfile_path = os.path.join(working_directory, pidfile_name)
        if os.path.exists(pidfile_path):
            self._warn('Pidfile %s already exists' % pidfile_path)
            os.remove(pidfile_path)

        subprocess.Popen(command, stdout=out_file, stderr=subprocess.STDOUT,
                         stdin=in_devnull)
        out_file.close()
        in_devnull.close()


    def write_to_file(self, file_path, contents):
        self._ensure_directory_exists(os.path.dirname(file_path))
        try:
            file_object = open(file_path, 'a')
            file_object.write(contents)
            file_object.close()
        except IOError, exc:
            self._warn('Error write to file %s: %s' % (file_path, exc))


    def copy_file_or_directory(self, source_path, destination_path):
        """
        This interface is designed to match server.hosts.abstract_ssh.get_file
        (and send_file).  That is, if the source_path ends with a slash, the
        contents of the directory are copied; otherwise, the directory iself is
        copied.
        """
        if source_path.rstrip('/') == destination_path.rstrip('/'):
            return
        self._ensure_directory_exists(os.path.dirname(destination_path))
        if source_path.endswith('/'):
            # copying a directory's contents to another directory
            assert os.path.isdir(source_path)
            assert os.path.isdir(destination_path)
            for filename in os.listdir(source_path):
                self.copy_file_or_directory(
                    os.path.join(source_path, filename),
                    os.path.join(destination_path, filename))
        elif os.path.isdir(source_path):
            shutil.copytree(source_path, destination_path, symlinks=True)
        elif os.path.islink(source_path):
            # copied from shutil.copytree()
            link_to = os.readlink(source_path)
            os.symlink(link_to, destination_path)
        else:
            shutil.copy(source_path, destination_path)


    def wait_for_all_async_commands(self):
        for subproc in self._subcommands:
            subproc.fork_waitfor()
        self._subcommands = []


    def _poll_async_commands(self):
        still_running = []
        for subproc in self._subcommands:
            if subproc.poll() is None:
                still_running.append(subproc)
        self._subcommands = still_running


    def _wait_for_some_async_commands(self):
        self._poll_async_commands()
        max_processes = scheduler_config.config.max_transfer_processes
        while len(self._subcommands) >= max_processes:
            time.sleep(1)
            self._poll_async_commands()


    def run_async_command(self, function, args):
        subproc = subcommand.subcommand(function, args)
        self._subcommands.append(subproc)
        subproc.fork_start()


    def _sync_get_file_from(self, hostname, source_path, destination_path):
        self._ensure_directory_exists(os.path.dirname(destination_path))
        host = create_host(hostname)
        host.get_file(source_path, destination_path, delete_dest=True)


    def get_file_from(self, hostname, source_path, destination_path):
        self.run_async_command(self._sync_get_file_from,
                               (hostname, source_path, destination_path))


    def _sync_send_file_to(self, hostname, source_path, destination_path,
                           can_fail):
        host = create_host(hostname)
        try:
            host.run('mkdir -p ' + os.path.dirname(destination_path))
            host.send_file(source_path, destination_path, delete_dest=True)
        except error.AutoservError:
            if not can_fail:
                raise

            if os.path.isdir(source_path):
                failed_file = os.path.join(source_path, _TRANSFER_FAILED_FILE)
                file_object = open(failed_file, 'w')
                try:
                    file_object.write('%s:%s\n%s\n%s' %
                                      (hostname, destination_path,
                                       datetime.datetime.now(),
                                       traceback.format_exc()))
                finally:
                    file_object.close()
            else:
                copy_to = destination_path + _TRANSFER_FAILED_FILE
                self._ensure_directory_exists(os.path.dirname(copy_to))
                self.copy_file_or_directory(source_path, copy_to)


    def send_file_to(self, hostname, source_path, destination_path,
                     can_fail=False):
        self.run_async_command(self._sync_send_file_to,
                               (hostname, source_path, destination_path,
                                can_fail))


    def _report_long_execution(self, calls, duration):
        call_count = {}
        for call in calls:
            call_count.setdefault(call._method, 0)
            call_count[call._method] += 1
        call_summary = '\n'.join('%d %s' % (count, method)
                                 for method, count in call_count.iteritems())
        self._warn('Execution took %f sec\n%s' % (duration, call_summary))


    def execute_calls(self, calls):
        results = []
        start_time = time.time()
        max_processes = scheduler_config.config.max_transfer_processes
        for method_call in calls:
            results.append(method_call.execute_on(self))
            if len(self._subcommands) >= max_processes:
                self._wait_for_some_async_commands()
        self.wait_for_all_async_commands()

        duration = time.time() - start_time
        if duration > self._WARNING_DURATION:
            self._report_long_execution(calls, duration)

        warnings = self.warnings
        self.warnings = []
        return dict(results=results, warnings=warnings)


def create_host(hostname):
    username = global_config.global_config.get_config_value(
        'SCHEDULER', hostname + '_username', default=getpass.getuser())
    return hosts.SSHHost(hostname, user=username)


def parse_input():
    input_chunks = []
    chunk_of_input = sys.stdin.read()
    while chunk_of_input:
        input_chunks.append(chunk_of_input)
        chunk_of_input = sys.stdin.read()
    pickled_input = ''.join(input_chunks)

    try:
        return pickle.loads(pickled_input)
    except Exception, exc:
        separator = '*' * 50
        raise ValueError('Unpickling input failed\n'
                         'Input: %r\n'
                         'Exception from pickle:\n'
                         '%s\n%s\n%s' %
                         (pickled_input, separator, traceback.format_exc(),
                          separator))


def return_data(data):
    print pickle.dumps(data)


def main():
    calls = parse_input()
    drone_utility = DroneUtility()
    return_value = drone_utility.execute_calls(calls)
    return_data(return_value)


if __name__ == '__main__':
    main()
