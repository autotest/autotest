#!/usr/bin/python2.4

import pickle, subprocess, os, shutil, socket, sys, time, signal, getpass
import datetime, traceback
import common
from autotest_lib.client.common_lib import utils, global_config, error
from autotest_lib.server import hosts, subcommand
from autotest_lib.scheduler import email_manager, scheduler_config

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
    _PS_ARGS = ['pid', 'pgid', 'ppid', 'comm', 'args']
    _WARNING_DURATION = 60

    def __init__(self):
        self.warnings = []
        self._subcommands = []


    def initialize(self, results_dir):
        temporary_directory = os.path.join(results_dir, _TEMPORARY_DIRECTORY)
        if os.path.exists(temporary_directory):
            shutil.rmtree(temporary_directory)
        self._ensure_directory_exists(temporary_directory)

        # make sure there are no old parsers running
        os.system('killall parse')


    def _warn(self, warning):
        self.warnings.append(warning)


    def _refresh_autoserv_processes(self):
        ps_proc = subprocess.Popen(
            ['/bin/ps', 'x', '-o', ','.join(self._PS_ARGS)],
            stdout=subprocess.PIPE)
        ps_output = ps_proc.communicate()[0]

        # split each line into the columns output by ps
        split_lines = [line.split(None, 4) for line in ps_output.splitlines()]
        process_infos = [dict(zip(self._PS_ARGS, line_components))
                         for line_components in split_lines]

        processes = []
        for info in process_infos:
            if info['comm'] == 'autoserv':
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
        results = {
            'pidfiles' : self._read_pidfiles(pidfile_paths),
            'processes' : self._refresh_autoserv_processes(),
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


    def _ensure_directory_exists(self, path):
        if not os.path.exists(path):
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


    def copy_file(self, source_path, destination_path):
        if source_path == destination_path:
            return
        self._ensure_directory_exists(os.path.dirname(destination_path))
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
                self.copy_file(source_path, copy_to)


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
