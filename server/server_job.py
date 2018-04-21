"""
The main job wrapper for the server side.

This is the core infrastructure. Derived from the client side job.py

Copyright Martin J. Bligh, Andy Whitcroft 2007
"""

import getpass
import os
import sys
import re
import tempfile
import time
import select
import platform
import traceback
import shutil
import warnings
import fcntl
import pickle
import logging
import itertools
import errno

from autotest.client import sysinfo
from autotest.client.shared import base_job
from autotest.client.shared import error
from autotest.client.shared import utils
from autotest.client.shared import packages
from autotest.client.shared import logging_manager
from autotest.server import test
from autotest.server import subcommand
from autotest.server import profilers
from autotest.server.hosts import abstract_ssh
from autotest.tko import dbutils
from autotest.tko import status_lib
from autotest.tko import utils as tko_utils  # pylint: disable=W0611
from autotest.frontend.tko import models_utils


def _control_segment_path(name):
    """Get the pathname of the named control segment file."""
    server_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(server_dir, "control_segments", name)


CLIENT_CONTROL_FILENAME = 'control'
SERVER_CONTROL_FILENAME = 'control.srv'
MACHINES_FILENAME = '.machines'

CLIENT_WRAPPER_CONTROL_FILE = _control_segment_path('client_wrapper')
CRASHDUMPS_CONTROL_FILE = _control_segment_path('crashdumps')
CRASHINFO_CONTROL_FILE = _control_segment_path('crashinfo')
INSTALL_CONTROL_FILE = _control_segment_path('install')
CLEANUP_CONTROL_FILE = _control_segment_path('cleanup')

VERIFY_CONTROL_FILE = _control_segment_path('verify')
REPAIR_CONTROL_FILE = _control_segment_path('repair')


# by default provide a stub that generates no site data
def _get_site_job_data_dummy(job):
    return {}


class status_indenter(base_job.status_indenter):

    """Provide a simple integer-backed status indenter."""

    def __init__(self):
        self._indent = 0

    @property
    def indent(self):
        return self._indent

    def increment(self):
        self._indent += 1

    def decrement(self):
        self._indent -= 1

    def get_context(self):
        """Returns a context object for use by job.get_record_context."""
        class context(object):

            def __init__(self, indenter, indent):
                self._indenter = indenter
                self._indent = indent

            def restore(self):
                self._indenter._indent = self._indent
        return context(self, self._indent)


class server_job_record_hook(object):

    """The job.record hook for server job. Used to inject WARN messages from
    the console or vlm whenever new logs are written, and to echo any logs
    to INFO level logging. Implemented as a class so that it can use state to
    block recursive calls, so that the hook can call job.record itself to
    log WARN messages.

    Depends on job._read_warnings and job._logger.
    """

    def __init__(self, job):
        self._job = job
        self._being_called = False

    def __call__(self, entry):
        """A wrapper around the 'real' record hook, the _hook method, which
        prevents recursion. This isn't making any effort to be threadsafe,
        the intent is to outright block infinite recursion via a
        job.record->_hook->job.record->_hook->job.record... chain."""
        if self._being_called:
            return
        self._being_called = True
        try:
            self._hook(self._job, entry)
        finally:
            self._being_called = False

    @staticmethod
    def _hook(job, entry):
        """The core hook, which can safely call job.record."""
        entries = []
        # poll all our warning loggers for new warnings
        for timestamp, msg in job._read_warnings():
            warning_entry = base_job.status_log_entry(
                'WARN', None, None, msg, {}, timestamp=timestamp)
            entries.append(warning_entry)
            job.record_entry(warning_entry)
        # echo rendered versions of all the status logs to info
        entries.append(entry)
        for entry in entries:
            rendered_entry = job._logger.render_entry(entry)
            logging.info(rendered_entry)
            job._parse_status(rendered_entry)


class base_server_job(base_job.base_job):

    """The server-side concrete implementation of base_job.

    Optional properties provided by this implementation:
        serverdir
        conmuxdir

        num_tests_run
        num_tests_failed

        warning_manager
        warning_loggers
    """

    _STATUS_VERSION = 1

    def __init__(self, control, args, resultdir, label, user, machines,
                 client=False, parse_job='',
                 ssh_user='root', ssh_port=22, ssh_pass='',
                 group_name='', tag='',
                 control_filename=SERVER_CONTROL_FILENAME):
        """
        Create a server side job object.

        :param control: The pathname of the control file.
        :param args: Passed to the control file.
        :param resultdir: Where to throw the results.
        :param label: Description of the job.
        :param user: Username for the job (email address).
        :param client: True if this is a client-side control file.
        :param parse_job: string, if supplied it is the job execution tag that
                the results will be passed through to the TKO parser with.
        :param ssh_user: The SSH username.  [root]
        :param ssh_port: The SSH port number.  [22]
        :param ssh_pass: The SSH passphrase, if needed.
        :param group_name: If supplied, this will be written out as
                host_group_name in the keyvals file for the parser.
        :param tag: The job execution tag from the scheduler.  [optional]
        :param control_filename: The filename where the server control file
                should be written in the results directory.
        """
        super(base_server_job, self).__init__(resultdir=resultdir)

        path = os.path.dirname(__file__)
        self.control = control
        self._uncollected_log_file = os.path.join(self.resultdir,
                                                  'uncollected_logs')
        debugdir = os.path.join(self.resultdir, 'debug')
        if not os.path.exists(debugdir):
            os.mkdir(debugdir)

        if user:
            self.user = user
        else:
            self.user = getpass.getuser()

        self.args = args
        self.machines = machines
        self._client = client
        self.warning_loggers = set()
        self.warning_manager = warning_manager()
        self._ssh_user = ssh_user
        self._ssh_port = ssh_port
        self._ssh_pass = ssh_pass
        self.tag = tag
        self.last_boot_tag = None
        self.hosts = set()
        self.drop_caches = False
        self.drop_caches_between_iterations = False
        self._control_filename = control_filename

        self.logging = logging_manager.get_logging_manager(
            manage_stdout_and_stderr=True, redirect_fds=True)
        subcommand.logging_manager_object = self.logging

        self.sysinfo = sysinfo.sysinfo(self.resultdir)
        self.profilers = profilers.profilers(self)

        job_data = {'label': label, 'user': user,
                    'hostname': ','.join(machines),
                    'drone': platform.node(),
                    'status_version': str(self._STATUS_VERSION),
                    'job_started': str(int(time.time()))}
        if group_name:
            job_data['host_group_name'] = group_name

        # only write these keyvals out on the first job in a resultdir
        if 'job_started' not in utils.read_keyval(self.resultdir):
            job_data.update(get_site_job_data(self))
            utils.write_keyval(self.resultdir, job_data)

        self._parse_job = parse_job
        self._using_parser = (self._parse_job and len(machines) <= 1)
        self.pkgmgr = packages.PackageManager(
            self.autodir, run_function_dargs={'timeout': 600})
        self.num_tests_run = 0
        self.num_tests_failed = 0

        self._register_subcommand_hooks()

        # these components aren't usable on the server
        self.bootloader = None
        self.harness = None

        # set up the status logger
        self._indenter = status_indenter()
        self._logger = base_job.status_logger(
            self, self._indenter, 'status.log', 'status.log',
            record_hook=server_job_record_hook(self))

    @classmethod
    # The unittests will hide this method, well, for unittesting
    # pylint: disable=E0202
    def _find_base_directories(cls):
        """
        Determine locations of autodir, clientdir and serverdir. Assumes
        that this file is located within serverdir and uses __file__ along
        with relative paths to resolve the location.
        """
        serverdir = os.path.abspath(os.path.dirname(__file__))
        autodir = os.path.normpath(os.path.join(serverdir, '..'))
        clientdir = os.path.join(autodir, 'client')
        return autodir, clientdir, serverdir

    # The unittests will hide this method, well, for unittesting
    # pylint: disable=E0202
    def _find_resultdir(self, resultdir):
        """
        Determine the location of resultdir. For server jobs we expect one to
        always be explicitly passed in to __init__, so just return that.
        """
        if resultdir:
            return os.path.normpath(resultdir)
        else:
            return None

    def _get_status_logger(self):
        """Return a reference to the status logger."""
        return self._logger

    @staticmethod
    def _load_control_file(path):
        f = open(path)
        try:
            control_file = f.read()
        finally:
            f.close()
        return re.sub('\r', '', control_file)

    def _register_subcommand_hooks(self):
        """
        Register some hooks into the subcommand modules that allow us
        to properly clean up self.hosts created in forked subprocesses.
        """
        def on_fork(cmd):
            self._existing_hosts_on_fork = set(self.hosts)

        def on_join(cmd):
            new_hosts = self.hosts - self._existing_hosts_on_fork
            for host in new_hosts:
                host.close()
        subcommand.subcommand.register_fork_hook(on_fork)
        subcommand.subcommand.register_join_hook(on_join)

    def init_parser(self):
        """
        Start the continuous parsing of self.resultdir. This sets up
        the database connection and inserts the basic job object into
        the database if necessary.
        """
        if not self._using_parser:
            return
        # create a job model object
        self.parser = status_lib.parser(self._STATUS_VERSION)
        self.job_model = self.parser.make_job(self.resultdir)
        self.parser.start(self.job_model)
        # check if a job already exists in the db and insert it if
        # it does not
        job_idx = models_utils.job_get_idx_by_tag(self._parse_job)
        if job_idx is None:
            dbutils.insert_job(self._parse_job, self.job_model)
        else:
            machine_idx = models_utils.machine_get_idx_by_hostname(
                self.job_model.machine)
            self.job_model.index = job_idx
            self.job_model.machine_idx = machine_idx

    def cleanup_parser(self):
        """
        This should be called after the server job is finished
        to carry out any remaining cleanup (e.g. flushing any
        remaining test results to the results db)
        """
        if not self._using_parser:
            return
        final_tests = self.parser.end()
        for test in final_tests:
            self.__insert_test(test)
        self._using_parser = False

    def verify(self):
        if not self.machines:
            raise error.AutoservError('No machines specified to verify')
        if self.resultdir:
            os.chdir(self.resultdir)
        try:
            namespace = {'machines': self.machines, 'job': self,
                         'ssh_user': self._ssh_user,
                         'ssh_port': self._ssh_port,
                         'ssh_pass': self._ssh_pass}
            self._execute_code(VERIFY_CONTROL_FILE, namespace, protect=False)
        except Exception, e:
            msg = ('Verify failed\n' + str(e) + '\n' + traceback.format_exc())
            self.record('ABORT', None, None, msg)
            raise

    def repair(self, host_protection):
        if not self.machines:
            raise error.AutoservError('No machines specified to repair')
        if self.resultdir:
            os.chdir(self.resultdir)
        namespace = {'machines': self.machines, 'job': self,
                     'ssh_user': self._ssh_user, 'ssh_port': self._ssh_port,
                     'ssh_pass': self._ssh_pass,
                     'protection_level': host_protection}

        self._execute_code(REPAIR_CONTROL_FILE, namespace, protect=False)

    def precheck(self):
        """
        perform any additional checks in derived classes.
        """
        pass

    def enable_external_logging(self):
        """
        Start or restart external logging mechanism.
        """
        pass

    def disable_external_logging(self):
        """
        Pause or stop external logging mechanism.
        """
        pass

    def use_external_logging(self):
        """
        Return True if external logging should be used.
        """
        return False

    def _make_parallel_wrapper(self, function, machines, log):
        """Wrap function as appropriate for calling by parallel_simple."""
        is_forking = not (len(machines) == 1 and self.machines == machines)
        if self._parse_job and is_forking and log:
            def wrapper(machine):
                self._parse_job += "/" + machine
                self._using_parser = True
                self.machines = [machine]
                self.push_execution_context(machine)
                os.chdir(self.resultdir)
                utils.write_keyval(self.resultdir, {"hostname": machine})
                self.init_parser()
                result = function(machine)
                self.cleanup_parser()
                return result
        elif len(machines) > 1 and log:
            def wrapper(machine):
                self.push_execution_context(machine)
                os.chdir(self.resultdir)
                machine_data = {'hostname': machine,
                                'status_version': str(self._STATUS_VERSION)}
                utils.write_keyval(self.resultdir, machine_data)
                result = function(machine)
                return result
        else:
            wrapper = function
        return wrapper

    def parallel_simple(self, function, machines, log=True, timeout=None,
                        return_results=False):
        """
        Run 'function' using parallel_simple, with an extra wrapper to handle
        the necessary setup for continuous parsing, if possible. If continuous
        parsing is already properly initialized then this should just work.

        :param function: A callable to run in parallel given each machine.
        :param machines: A list of machine names to be passed one per subcommand
                invocation of function.
        :param log: If True, output will be written to output in a subdirectory
                named after each machine.
        :param timeout: Seconds after which the function call should timeout.
        :param return_results: If True instead of an AutoServError being raised
                on any error a list of the results|exceptions from the function
                called on each arg is returned.  [default: False]

        :raise error.AutotestError: If any of the functions failed.
        """
        wrapper = self._make_parallel_wrapper(function, machines, log)
        return subcommand.parallel_simple(wrapper, machines,
                                          log=log, timeout=timeout,
                                          return_results=return_results)

    def parallel_on_machines(self, function, machines, timeout=None):
        """
        :param function: Called in parallel with one machine as its argument.
        :param machines: A list of machines to call function(machine) on.
        :param timeout: Seconds after which the function call should timeout.

        :return: A list of machines on which function(machine) returned
                without raising an exception.
        """
        results = self.parallel_simple(function, machines, timeout=timeout,
                                       return_results=True)
        success_machines = []
        for result, machine in itertools.izip(results, machines):
            if not isinstance(result, Exception):
                success_machines.append(machine)
        return success_machines

    _USE_TEMP_DIR = object()

    def run(self, cleanup=False, install_before=False, install_after=False,
            collect_crashdumps=True, namespace={}, control=None,
            control_file_dir=None, only_collect_crashinfo=False):
        # for a normal job, make sure the uncollected logs file exists
        # for a crashinfo-only run it should already exist, bail out otherwise
        created_uncollected_logs = False
        if self.resultdir and not os.path.exists(self._uncollected_log_file):
            if only_collect_crashinfo:
                # if this is a crashinfo-only run, and there were no existing
                # uncollected logs, just bail out early
                logging.info("No existing uncollected logs, "
                             "skipping crashinfo collection")
                return
            else:
                log_file = open(self._uncollected_log_file, "w")
                pickle.dump([], log_file)
                log_file.close()
                created_uncollected_logs = True

        # use a copy so changes don't affect the original dictionary
        namespace = namespace.copy()
        machines = self.machines
        if control is None:
            if self.control is None:
                control = ''
            else:
                control = self._load_control_file(self.control)
        if control_file_dir is None:
            control_file_dir = self.resultdir

        self.aborted = False
        namespace['machines'] = machines
        namespace['args'] = self.args
        namespace['job'] = self
        namespace['ssh_user'] = self._ssh_user
        namespace['ssh_port'] = self._ssh_port
        namespace['ssh_pass'] = self._ssh_pass
        test_start_time = int(time.time())

        if self.resultdir:
            os.chdir(self.resultdir)
            # touch status.log so that the parser knows a job is running here
            open(self.get_status_log_path(), 'a').close()
            self.enable_external_logging()

        collect_crashinfo = True
        temp_control_file_dir = None
        try:
            try:
                if install_before and machines:
                    self._execute_code(INSTALL_CONTROL_FILE, namespace)

                if only_collect_crashinfo:
                    return

                # determine the dir to write the control files to
                cfd_specified = (control_file_dir and control_file_dir is not
                                 self._USE_TEMP_DIR)
                if cfd_specified:
                    temp_control_file_dir = None
                else:
                    temp_control_file_dir = tempfile.mkdtemp(
                        suffix='temp_control_file_dir')
                    control_file_dir = temp_control_file_dir
                server_control_file = os.path.join(control_file_dir,
                                                   self._control_filename)
                client_control_file = os.path.join(control_file_dir,
                                                   CLIENT_CONTROL_FILENAME)
                if self._client:
                    namespace['control'] = control
                    utils.open_write_close(client_control_file, control)
                    shutil.copyfile(CLIENT_WRAPPER_CONTROL_FILE,
                                    server_control_file)
                else:
                    utils.open_write_close(server_control_file, control)
                logging.info("Processing control file")
                self._execute_code(server_control_file, namespace)
                logging.info("Finished processing control file")

                # no error occurred, so we don't need to collect crashinfo
                collect_crashinfo = False
            except Exception, e:
                try:
                    logging.exception(
                        'Exception escaped control file, job aborting:')
                    self.record('INFO', None, None, str(e),
                                {'job_abort_reason': str(e)})
                except Exception:
                    pass  # don't let logging exceptions here interfere
                raise
        finally:
            if temp_control_file_dir:
                # Clean up temp directory used for copies of the control files
                try:
                    shutil.rmtree(temp_control_file_dir)
                except Exception, e:
                    logging.warn('Could not remove temp directory %s: %s',
                                 temp_control_file_dir, e)

            if machines and (collect_crashdumps or collect_crashinfo):
                namespace['test_start_time'] = test_start_time
                if collect_crashinfo:
                    # includes crashdumps
                    self._execute_code(CRASHINFO_CONTROL_FILE, namespace)
                else:
                    self._execute_code(CRASHDUMPS_CONTROL_FILE, namespace)
            if self._uncollected_log_file and created_uncollected_logs:
                os.remove(self._uncollected_log_file)
            self.disable_external_logging()
            if cleanup and machines:
                self._execute_code(CLEANUP_CONTROL_FILE, namespace)
            if install_after and machines:
                self._execute_code(INSTALL_CONTROL_FILE, namespace)

    def run_test(self, url, *args, **dargs):
        """
        Summon a test object and run it.

        tag
                tag to add to testname
        url
                url of the test to run
        """
        group, testname = self.pkgmgr.get_package_name(url, 'test')
        testname, subdir, tag = self._build_tagged_test_name(testname, dargs)
        outputdir = self._make_test_outputdir(subdir)

        def group_func():
            try:
                test.runtest(self, url, tag, args, dargs)
            except error.TestBaseException, e:
                self.record(e.exit_status, subdir, testname, str(e))
                raise
            except Exception, e:
                info = str(e) + "\n" + traceback.format_exc()
                self.record('FAIL', subdir, testname, info)
                raise
            else:
                self.record('GOOD', subdir, testname, 'completed successfully')

        result, exc_info = self._run_group(testname, subdir, group_func)
        if exc_info and isinstance(exc_info[1], error.TestBaseException):
            return False
        elif exc_info:
            raise exc_info[0], exc_info[1], exc_info[2]
        else:
            return True

    def _run_group(self, name, subdir, function, *args, **dargs):
        """
        Underlying method for running something inside of a group.
        """
        result, exc_info = None, None
        try:
            self.record('START', subdir, name)
            result = function(*args, **dargs)
        except error.TestBaseException, e:
            self.record("END %s" % e.exit_status, subdir, name)
            exc_info = sys.exc_info()
        except Exception, e:
            err_msg = str(e) + '\n'
            err_msg += traceback.format_exc()
            self.record('END ABORT', subdir, name, err_msg)
            raise error.JobError(name + ' failed\n' + traceback.format_exc())
        else:
            self.record('END GOOD', subdir, name)

        return result, exc_info

    def run_group(self, function, *args, **dargs):
        """
        function:
                subroutine to run
        *args:
                arguments for the function
        """

        name = function.__name__

        # Allow the tag for the group to be specified.
        tag = dargs.pop('tag', None)
        if tag:
            name = tag

        return self._run_group(name, None, function, *args, **dargs)[0]

    def run_reboot(self, reboot_func, get_kernel_func):
        """
        A specialization of run_group meant specifically for handling
        a reboot. Includes support for capturing the kernel version
        after the reboot.

        reboot_func: a function that carries out the reboot

        get_kernel_func: a function that returns a string
        representing the kernel version.
        """
        try:
            self.record('START', None, 'reboot')
            reboot_func()
        except Exception, e:
            err_msg = str(e) + '\n' + traceback.format_exc()
            self.record('END FAIL', None, 'reboot', err_msg)
            raise
        else:
            kernel = get_kernel_func()
            self.record('END GOOD', None, 'reboot',
                        optional_fields={"kernel": kernel})

    def run_control(self, path):
        """Execute a control file found at path (relative to the autotest
        path). Intended for executing a control file within a control file,
        not for running the top-level job control file."""
        path = os.path.join(self.autodir, path)
        control_file = self._load_control_file(path)
        self.run(control=control_file, control_file_dir=self._USE_TEMP_DIR)

    def add_sysinfo_command(self, command, logfile=None, on_every_test=False):
        self._add_sysinfo_loggable(sysinfo.command(command, logf=logfile),
                                   on_every_test)

    def add_sysinfo_logfile(self, file, on_every_test=False):
        self._add_sysinfo_loggable(sysinfo.logfile(file), on_every_test)

    def _add_sysinfo_loggable(self, loggable, on_every_test):
        if on_every_test:
            self.sysinfo.test_loggables.add(loggable)
        else:
            self.sysinfo.boot_loggables.add(loggable)

    def _read_warnings(self):
        """Poll all the warning loggers and extract any new warnings that have
        been logged. If the warnings belong to a category that is currently
        disabled, this method will discard them and they will no longer be
        retrievable.

        Returns a list of (timestamp, message) tuples, where timestamp is an
        integer epoch timestamp."""
        warnings = []
        while True:
            # pull in a line of output from every logger that has
            # output ready to be read
            loggers, _, _ = select.select(self.warning_loggers, [], [], 0)
            closed_loggers = set()
            for logger in loggers:
                line = logger.readline()
                # record any broken pipes (aka line == empty)
                if len(line) == 0:
                    closed_loggers.add(logger)
                    continue
                # parse out the warning
                timestamp, msgtype, msg = line.split('\t', 2)
                timestamp = int(timestamp)
                # if the warning is valid, add it to the results
                if self.warning_manager.is_valid(timestamp, msgtype):
                    warnings.append((timestamp, msg.strip()))

            # stop listening to loggers that are closed
            self.warning_loggers -= closed_loggers

            # stop if none of the loggers have any output left
            if not loggers:
                break

        # sort into timestamp order
        warnings.sort()
        return warnings

    def _unique_subdirectory(self, base_subdirectory_name):
        """Compute a unique results subdirectory based on the given name.

        Appends base_subdirectory_name with a number as necessary to find a
        directory name that doesn't already exist.
        """
        subdirectory = base_subdirectory_name
        counter = 1
        while os.path.exists(os.path.join(self.resultdir, subdirectory)):
            subdirectory = base_subdirectory_name + '.' + str(counter)
            counter += 1
        return subdirectory

    def get_record_context(self):
        """Returns an object representing the current job.record context.

        The object returned is an opaque object with a 0-arg restore method
        which can be called to restore the job.record context (i.e. indentation)
        to the current level. The intention is that it should be used when
        something external which generate job.record calls (e.g. an autotest
        client) can fail catastrophically and the server job record state
        needs to be reset to its original "known good" state.

        :return: A context object with a 0-arg restore() method."""
        return self._indenter.get_context()

    def record_summary(self, status_code, test_name, reason='', attributes=None,
                       distinguishing_attributes=(), child_test_ids=None):
        """Record a summary test result.

        :param status_code: status code string, see
                shared.log.is_valid_status()
        :param test_name: name of the test
        :param reason: (optional) string providing detailed reason for test
                outcome
        :param attributes: (optional) dict of string keyvals to associate with
                this result
        :param distinguishing_attributes: (optional) list of attribute names
                that should be used to distinguish identically-named test
                results.  These attributes should be present in the attributes
                parameter.  This is used to generate user-friendly subdirectory
                names.
        :param child_test_ids: (optional) list of test indices for test results
                used in generating this result.
        """
        subdirectory_name_parts = [test_name]
        for attribute in distinguishing_attributes:
            assert attributes
            assert attribute in attributes, '%s not in %s' % (attribute,
                                                              attributes)
            subdirectory_name_parts.append(attributes[attribute])
        base_subdirectory_name = '.'.join(subdirectory_name_parts)

        subdirectory = self._unique_subdirectory(base_subdirectory_name)
        subdirectory_path = os.path.join(self.resultdir, subdirectory)
        os.mkdir(subdirectory_path)

        self.record(status_code, subdirectory, test_name,
                    status=reason, optional_fields={'is_summary': True})

        if attributes:
            utils.write_keyval(subdirectory_path, attributes)

        if child_test_ids:
            ids_string = ','.join(str(test_id) for test_id in child_test_ids)
            summary_data = {'child_test_ids': ids_string}
            utils.write_keyval(os.path.join(subdirectory_path, 'summary_data'),
                               summary_data)

    def disable_warnings(self, warning_type):
        self.warning_manager.disable_warnings(warning_type)
        self.record("INFO", None, None,
                    "disabling %s warnings" % warning_type,
                    {"warnings.disable": warning_type})

    def enable_warnings(self, warning_type):
        self.warning_manager.enable_warnings(warning_type)
        self.record("INFO", None, None,
                    "enabling %s warnings" % warning_type,
                    {"warnings.enable": warning_type})

    def get_status_log_path(self, subdir=None):
        """Return the path to the job status log.

        :param subdir - Optional parameter indicating that you want the path
            to a subdirectory status log.

        :return: The path where the status log should be.
        """
        if self.resultdir:
            if subdir:
                return os.path.join(self.resultdir, subdir, "status.log")
            else:
                return os.path.join(self.resultdir, "status.log")
        else:
            return None

    def _update_uncollected_logs_list(self, update_func):
        """Updates the uncollected logs list in a multi-process safe manner.

        :param update_func - a function that updates the list of uncollected
            logs. Should take one parameter, the list to be updated.
        """
        if self._uncollected_log_file:
            log_file = open(self._uncollected_log_file, "r+")
            fcntl.flock(log_file, fcntl.LOCK_EX)
        try:
            uncollected_logs = pickle.load(log_file)
            update_func(uncollected_logs)
            log_file.seek(0)
            log_file.truncate()
            pickle.dump(uncollected_logs, log_file)
            log_file.flush()
        finally:
            fcntl.flock(log_file, fcntl.LOCK_UN)
            log_file.close()

    def add_client_log(self, hostname, remote_path, local_path):
        """Adds a new set of client logs to the list of uncollected logs,
        to allow for future log recovery.

        :param host - the hostname of the machine holding the logs
        :param remote_path - the directory on the remote machine holding logs
        :param local_path - the local directory to copy the logs into
        """
        def update_func(logs_list):
            logs_list.append((hostname, remote_path, local_path))
        self._update_uncollected_logs_list(update_func)

    def remove_client_log(self, hostname, remote_path, local_path):
        """Removes a set of client logs from the list of uncollected logs,
        to allow for future log recovery.

        :param host - the hostname of the machine holding the logs
        :param remote_path - the directory on the remote machine holding logs
        :param local_path - the local directory to copy the logs into
        """
        def update_func(logs_list):
            logs_list.remove((hostname, remote_path, local_path))
        self._update_uncollected_logs_list(update_func)

    def get_client_logs(self):
        """Retrieves the list of uncollected logs, if it exists.

        :return: A list of (host, remote_path, local_path) tuples. Returns
                 an empty list if no uncollected logs file exists.
        """
        log_exists = (self._uncollected_log_file and
                      os.path.exists(self._uncollected_log_file))
        if log_exists:
            return pickle.load(open(self._uncollected_log_file))
        else:
            return []

    def _fill_server_control_namespace(self, namespace, protect=True):
        """
        Prepare a namespace to be used when executing server control files.

        This sets up the control file API by importing modules and making them
        available under the appropriate names within namespace.

        For use by _execute_code().

        Args:
          namespace: The namespace dictionary to fill in.
          protect: Boolean.  If True (the default) any operation that would
              clobber an existing entry in namespace will cause an error.
        Raises:
          error.AutoservError: When a name would be clobbered by import.
        """
        def _import_names(module_name, names=()):
            """
            Import a module and assign named attributes into namespace.

            Args:
                module_name: The string module name.
                names: A limiting list of names to import from module_name.  If
                    empty (the default), all names are imported from the module
                    similar to a "from foo.bar import *" statement.
            Raises:
                error.AutoservError: When a name being imported would clobber
                    a name already in namespace.
            """
            module = __import__(module_name, {}, {}, names)

            # No names supplied?  Import * from the lowest level module.
            # (Ugh, why do I have to implement this part myself?)
            if not names:
                for submodule_name in module_name.split('.')[1:]:
                    module = getattr(module, submodule_name)
                if hasattr(module, '__all__'):
                    names = getattr(module, '__all__')
                else:
                    names = dir(module)

            # Install each name into namespace, checking to make sure it
            # doesn't override anything that already exists.
            for name in names:
                # Check for conflicts to help prevent future problems.
                if name in namespace and protect:
                    if namespace[name] is not getattr(module, name):
                        raise error.AutoservError('importing name '
                                                  '%s from %s %r would override %r' %
                                                  (name, module_name, getattr(module, name),
                                                   namespace[name]))
                    else:
                        # Encourage cleanliness and the use of __all__ for a
                        # more concrete API with less surprises on '*' imports.
                        warnings.warn('%s (%r) being imported from %s for use '
                                      'in server control files is not the '
                                      'first occurrence of that import.' %
                                      (name, namespace[name], module_name))

                namespace[name] = getattr(module, name)

        # This is the equivalent of prepending a bunch of import statements to
        # the front of the control script.
        namespace.update(os=os, sys=sys, logging=logging)
        _import_names('autotest.server',
                      ('hosts', 'autotest_remote', 'standalone_profiler',
                       'source_kernel', 'rpm_kernel', 'deb_kernel', 'git_kernel'))
        _import_names('autotest.server.subcommand',
                      ('parallel', 'parallel_simple', 'subcommand'))
        _import_names('autotest.server.utils',
                      ('run', 'get_tmp_dir', 'sh_escape', 'parse_machine'))
        _import_names('autotest.client.shared.error')
        _import_names('autotest.client.shared.barrier', ('barrier',))

        # Inject ourself as the job object into other classes within the API.
        # (Yuck, this injection is a gross thing be part of a public API. -gps)
        #
        # XXX Base & SiteAutotest do not appear to use .job.  Who does?
        namespace['autotest_remote'].Autotest.job = self
        # server.hosts.base_classes.Host uses .job.
        namespace['hosts'].Host.job = self
        namespace['hosts'].factory.ssh_user = self._ssh_user
        namespace['hosts'].factory.ssh_port = self._ssh_port
        namespace['hosts'].factory.ssh_pass = self._ssh_pass

    def _execute_code(self, code_file, namespace, protect=True):
        """
        Execute code using a copy of namespace as a server control script.

        Unless protect_namespace is explicitly set to False, the dict will not
        be modified.

        Args:
          code_file: The filename of the control file to execute.
          namespace: A dict containing names to make available during execution.
          protect: Boolean.  If True (the default) a copy of the namespace dict
              is used during execution to prevent the code from modifying its
              contents outside of this function.  If False the raw dict is
              passed in and modifications will be allowed.
        """
        if protect:
            namespace = namespace.copy()
        self._fill_server_control_namespace(namespace, protect=protect)
        # TODO: Simplify and get rid of the special cases for only 1 machine.
        if len(self.machines) > 1:
            machines_text = '\n'.join(self.machines) + '\n'
            # Only rewrite the file if it does not match our machine list.
            try:
                machines_f = open(MACHINES_FILENAME, 'r')
                existing_machines_text = machines_f.read()
                machines_f.close()
            except EnvironmentError:
                existing_machines_text = None
            if machines_text != existing_machines_text:
                utils.open_write_close(MACHINES_FILENAME, machines_text)
        execfile(code_file, namespace, namespace)

    def _parse_status(self, new_line):
        if not self._using_parser:
            return
        new_tests = self.parser.process_lines([new_line])
        for test in new_tests:
            self.__insert_test(test)

    def __insert_test(self, test):
        """
        An internal method to insert a new test result into the
        database. This method will not raise an exception, even if an
        error occurs during the insert, to avoid failing a test
        simply because of unexpected database issues."""
        self.num_tests_run += 1
        if status_lib.is_worse_than_or_equal_to(test.status, 'FAIL'):
            self.num_tests_failed += 1
        try:
            dbutils.insert_test(self.job_model, test)
        except Exception:
            msg = ("WARNING: An unexpected error occurred while "
                   "inserting test results into the database. "
                   "Ignoring error.\n" + traceback.format_exc())
            print(msg, file=sys.stderr)

    def preprocess_client_state(self):
        """
        Produce a state file for initializing the state of a client job.

        Creates a new client state file with all the current server state, as
        well as some pre-set client state.

        :return: The path of the file the state was written into.
        """
        # initialize the sysinfo state
        self._state.set('client', 'sysinfo', self.sysinfo.serialize())

        # dump the state out to a tempfile
        fd, file_path = tempfile.mkstemp(dir=self.tmpdir)
        os.close(fd)

        # write_to_file doesn't need locking, we exclusively own file_path
        self._state.write_to_file(file_path)
        return file_path

    def postprocess_client_state(self, state_path):
        """
        Update the state of this job with the state from a client job.

        Updates the state of the server side of a job with the final state
        of a client job that was run. Updates the non-client-specific state,
        pulls in some specific bits from the client-specific state, and then
        discards the rest. Removes the state file afterwards

        :param state_file A path to the state file from the client.
        """
        # update the on-disk state
        try:
            self._state.read_from_file(state_path)
            os.remove(state_path)
        except OSError, e:
            # ignore file-not-found errors
            if e.errno != errno.ENOENT:
                raise
            else:
                logging.debug('Client state file %s not found', state_path)

        # update the sysinfo state
        if self._state.has('client', 'sysinfo'):
            self.sysinfo.deserialize(self._state.get('client', 'sysinfo'))

        # drop all the client-specific state
        self._state.discard_namespace('client')

    def clear_all_known_hosts(self):
        """Clears known hosts files for all AbstractSSHHosts."""
        for host in self.hosts:
            if isinstance(host, abstract_ssh.AbstractSSHHost):
                host.clear_known_hosts()


class warning_manager(object):

    """Class for controlling warning logs. Manages the enabling and disabling
    of warnings."""

    def __init__(self):
        # a map of warning types to a list of disabled time intervals
        self.disabled_warnings = {}

    def is_valid(self, timestamp, warning_type):
        """Indicates if a warning (based on the time it occurred and its type)
        is a valid warning. A warning is considered "invalid" if this type of
        warning was marked as "disabled" at the time the warning occurred."""
        disabled_intervals = self.disabled_warnings.get(warning_type, [])
        for start, end in disabled_intervals:
            if timestamp >= start and (end is None or timestamp < end):
                return False
        return True

    def disable_warnings(self, warning_type, current_time_func=time.time):
        """As of now, disables all further warnings of this type."""
        intervals = self.disabled_warnings.setdefault(warning_type, [])
        if not intervals or intervals[-1][1] is not None:
            intervals.append((int(current_time_func()), None))

    def enable_warnings(self, warning_type, current_time_func=time.time):
        """As of now, enables all further warnings of this type."""
        intervals = self.disabled_warnings.get(warning_type, [])
        if intervals and intervals[-1][1] is None:
            intervals[-1] = (intervals[-1][0], int(current_time_func()))


# load up site-specific code for generating site-specific job data
get_site_job_data = utils.import_site_function(__file__,
                                               "autotest.server.site_server_job", "get_site_job_data",
                                               _get_site_job_data_dummy)


site_server_job = utils.import_site_class(
    __file__, "autotest.server.site_server_job", "site_server_job",
    base_server_job)


class server_job(site_server_job):
    pass
