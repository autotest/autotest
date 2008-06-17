"""
The main job wrapper for the server side.

This is the core infrastructure. Derived from the client side job.py

Copyright Martin J. Bligh, Andy Whitcroft 2007
"""

__author__ = """
Martin J. Bligh <mbligh@google.com>
Andy Whitcroft <apw@shadowen.org>
"""

import os, sys, re, time, select, subprocess, traceback

from autotest_lib.client.bin import fd_stack
from autotest_lib.client.common_lib import error, logging
from autotest_lib.server import test, subcommand
from autotest_lib.tko import db as tko_db, status_lib, utils as tko_utils
from autotest_lib.client.common_lib import utils


# load up a control segment
# these are all stored in <server_dir>/control_segments
def load_control_segment(name):
    server_dir = os.path.dirname(os.path.abspath(__file__))
    script_file = os.path.join(server_dir, "control_segments", name)
    if os.path.exists(script_file):
        return file(script_file).read()
    else:
        return ""


preamble = """\
import os, sys

from autotest_lib.server import hosts, autotest, kvm, git, standalone_profiler
from autotest_lib.server import source_kernel, rpm_kernel, deb_kernel
from autotest_lib.server import git_kernel
from autotest_lib.server.subcommand import *
from autotest_lib.server.utils import run, get_tmp_dir, sh_escape
from autotest_lib.server.utils import parse_machine
from autotest_lib.client.common_lib.error import *
from autotest_lib.client.common_lib import barrier

autotest.Autotest.job = job
hosts.SSHHost.job = job
barrier = barrier.barrier
if len(machines) > 1:
        open('.machines', 'w').write('\\n'.join(machines) + '\\n')
"""

client_wrapper = """
at = autotest.Autotest()

def run_client(machine):
        hostname, user, password, port = parse_machine(machine,
                ssh_user, ssh_port, ssh_pass)

        host = hosts.SSHHost(hostname, user, port, password=password)
        at.run(control, host=host)

job.parallel_simple(run_client, machines)
"""

crashdumps = """
def crashdumps(machine):
        hostname, user, password, port = parse_machine(machine,
                ssh_user, ssh_port, ssh_pass)

        host = hosts.SSHHost(hostname, user, port, initialize=False, \
            password=password)
        host.get_crashdumps(test_start_time)

job.parallel_simple(crashdumps, machines, log=False)
"""

reboot_segment="""\
def reboot(machine):
        hostname, user, password, port = parse_machine(machine,
                ssh_user, ssh_port, ssh_pass)

        host = hosts.SSHHost(hostname, user, port, initialize=False, \
            password=password)
        host.reboot()

job.parallel_simple(reboot, machines, log=False)
"""

install="""\
def install(machine):
        hostname, user, password, port = parse_machine(machine,
                ssh_user, ssh_port, ssh_pass)

        host = hosts.SSHHost(hostname, user, port, initialize=False, \
            password=password)
        host.machine_install()

job.parallel_simple(install, machines, log=False)
"""

# load up the verifier control segment, with an optional site-specific hook
verify = load_control_segment("site_verify")
verify += load_control_segment("verify")

# load up the repair control segment, with an optional site-specific hook
repair = load_control_segment("site_repair")
repair += load_control_segment("repair")


# load up site-specific code for generating site-specific job data
try:
    import site_job
    get_site_job_data = site_job.get_site_job_data
    del site_job
except ImportError:
    # by default provide a stub that generates no site data
    def get_site_job_data(job):
        return {}


class base_server_job:
    """The actual job against which we do everything.

    Properties:
            autodir
                    The top level autotest directory (/usr/local/autotest).
            serverdir
                    <autodir>/server/
            clientdir
                    <autodir>/client/
            conmuxdir
                    <autodir>/conmux/
            testdir
                    <autodir>/server/tests/
            site_testdir
                    <autodir>/server/site_tests/
            control
                    the control file for this job
    """

    STATUS_VERSION = 1


    def __init__(self, control, args, resultdir, label, user, machines,
                 client=False, parse_job="",
                 ssh_user='root', ssh_port=22, ssh_pass=''):
        """
                control
                        The control file (pathname of)
                args
                        args to pass to the control file
                resultdir
                        where to throw the results
                label
                        label for the job
                user
                        Username for the job (email address)
                client
                        True if a client-side control file
        """
        path = os.path.dirname(__file__)
        self.autodir = os.path.abspath(os.path.join(path, '..'))
        self.serverdir = os.path.join(self.autodir, 'server')
        self.testdir   = os.path.join(self.serverdir, 'tests')
        self.site_testdir = os.path.join(self.serverdir, 'site_tests')
        self.tmpdir    = os.path.join(self.serverdir, 'tmp')
        self.conmuxdir = os.path.join(self.autodir, 'conmux')
        self.clientdir = os.path.join(self.autodir, 'client')
        self.toolsdir = os.path.join(self.autodir, 'client/tools')
        if control:
            self.control = open(control, 'r').read()
            self.control = re.sub('\r', '', self.control)
        else:
            self.control = None
        self.resultdir = resultdir
        if not os.path.exists(resultdir):
            os.mkdir(resultdir)
        self.debugdir = os.path.join(resultdir, 'debug')
        if not os.path.exists(self.debugdir):
            os.mkdir(self.debugdir)
        self.status = os.path.join(resultdir, 'status')
        self.label = label
        self.user = user
        self.args = args
        self.machines = machines
        self.client = client
        self.record_prefix = ''
        self.warning_loggers = set()
        self.ssh_user = ssh_user
        self.ssh_port = ssh_port
        self.ssh_pass = ssh_pass

        self.stdout = fd_stack.fd_stack(1, sys.stdout)
        self.stderr = fd_stack.fd_stack(2, sys.stderr)

        if os.path.exists(self.status):
            os.unlink(self.status)
        job_data = {'label' : label, 'user' : user,
                    'hostname' : ','.join(machines),
                    'status_version' : str(self.STATUS_VERSION)}
        job_data.update(get_site_job_data(self))
        utils.write_keyval(self.resultdir, job_data)

        self.parse_job = parse_job
        if self.parse_job and len(machines) == 1:
            self.using_parser = True
            self.init_parser(resultdir)
        else:
            self.using_parser = False


    def init_parser(self, resultdir):
        """Start the continuous parsing of resultdir. This sets up
        the database connection and inserts the basic job object into
        the database if necessary."""
        # redirect parser debugging to .parse.log
        parse_log = os.path.join(resultdir, '.parse.log')
        parse_log = open(parse_log, 'w', 0)
        tko_utils.redirect_parser_debugging(parse_log)
        # create a job model object and set up the db
        self.results_db = tko_db.db(autocommit=True)
        self.parser = status_lib.parser(self.STATUS_VERSION)
        self.job_model = self.parser.make_job(resultdir)
        self.parser.start(self.job_model)
        # check if a job already exists in the db and insert it if
        # it does not
        job_idx = self.results_db.find_job(self.parse_job)
        if job_idx is None:
            self.results_db.insert_job(self.parse_job,
                                       self.job_model)
        else:
            machine_idx = self.results_db.lookup_machine(
                self.job_model.machine)
            self.job_model.index = job_idx
            self.job_model.machine_idx = machine_idx


    def cleanup_parser(self):
        """This should be called after the server job is finished
        to carry out any remaining cleanup (e.g. flushing any
        remaining test results to the results db)"""
        if not self.using_parser:
            return
        final_tests = self.parser.end()
        for test in final_tests:
            self.__insert_test(test)
        self.using_parser = False


    def verify(self):
        if not self.machines:
            raise error.AutoservError(
                'No machines specified to verify')
        try:
            namespace = {'machines' : self.machines, 'job' : self, \
                                     'ssh_user' : self.ssh_user, \
                                     'ssh_port' : self.ssh_port, \
                                     'ssh_pass' : self.ssh_pass}
            self._execute_code(preamble + verify, namespace, namespace)
        except Exception, e:
            msg = ('Verify failed\n' + str(e) + '\n'
                    + traceback.format_exc())
            self.record('ABORT', None, None, msg)
            raise


    def repair(self):
        if not self.machines:
            raise error.AutoservError(
                'No machines specified to repair')
        namespace = {'machines' : self.machines, 'job' : self, \
                                 'ssh_user' : self.ssh_user, \
                                 'ssh_port' : self.ssh_port, \
                                 'ssh_pass' : self.ssh_pass}
        # no matter what happens during repair, go on to try to reverify
        try:
            self._execute_code(preamble + repair, namespace, namespace)
        except Exception, exc:
            print 'Exception occured during repair'
            traceback.print_exc()
        self.verify()


    def enable_external_logging(self):
        """Start or restart external logging mechanism.
        """
        pass


    def disable_external_logging(self):
        """ Pause or stop external logging mechanism.
        """
        pass


    def use_external_logging(self):
        """Return True if external logging should be used.
        """
        return False


    def parallel_simple(self, function, machines, log=True, timeout=None):
        """Run 'function' using parallel_simple, with an extra
        wrapper to handle the necessary setup for continuous parsing,
        if possible. If continuous parsing is already properly
        initialized then this should just work."""
        is_forking = not (len(machines) == 1 and
                          self.machines == machines)
        if self.parse_job and is_forking:
            def wrapper(machine):
                self.parse_job += "/" + machine
                self.using_parser = True
                self.machines = [machine]
                self.resultdir = os.path.join(self.resultdir,
                                              machine)
                self.init_parser(self.resultdir)
                result = function(machine)
                self.cleanup_parser()
                return result
        else:
            wrapper = function
        subcommand.parallel_simple(wrapper, machines, log, timeout)


    def run(self, reboot = False, install_before = False,
            install_after = False, collect_crashdumps = True,
            namespace = {}):
        # use a copy so changes don't affect the original dictionary
        namespace = namespace.copy()
        machines = self.machines

        self.aborted = False
        namespace['machines'] = machines
        namespace['args'] = self.args
        namespace['job'] = self
        namespace['ssh_user'] = self.ssh_user
        namespace['ssh_port'] = self.ssh_port
        namespace['ssh_pass'] = self.ssh_pass
        test_start_time = int(time.time())

        os.chdir(self.resultdir)

        self.enable_external_logging()
        status_log = os.path.join(self.resultdir, 'status.log')
        try:
            if install_before and machines:
                self._execute_code(preamble + install, namespace, namespace)
            if self.client:
                namespace['control'] = self.control
                open('control', 'w').write(self.control)
                open('control.srv', 'w').write(client_wrapper)
                server_control = client_wrapper
            else:
                open('control.srv', 'w').write(self.control)
                server_control = self.control
            self._execute_code(preamble + server_control, namespace,
                                   namespace)

        finally:
            if machines and collect_crashdumps:
                namespace['test_start_time'] = test_start_time
                self._execute_code(preamble + crashdumps, namespace,
                                       namespace)
            self.disable_external_logging()
            if reboot and machines:
                self._execute_code(preamble + reboot_segment,namespace,
                                       namespace)
            if install_after and machines:
                self._execute_code(preamble + install, namespace, namespace)


    def run_test(self, url, *args, **dargs):
        """Summon a test object and run it.

        tag
                tag to add to testname
        url
                url of the test to run
        """

        (group, testname) = test.testname(url)
        tag = None
        subdir = testname

        if dargs.has_key('tag'):
            tag = dargs['tag']
            del dargs['tag']
            if tag:
                subdir += '.' + tag

        outputdir = os.path.join(self.resultdir, subdir)
        if os.path.exists(outputdir):
            msg = ("%s already exists, test <%s> may have"
                   " already run with tag <%s>"
                   % (outputdir, testname, tag) )
            raise error.TestError(msg)
        os.mkdir(outputdir)

        try:
            test.runtest(self, url, tag, args, dargs)
            self.record('GOOD', subdir, testname, 'completed successfully')
        except error.TestNAError, detail:
            self.record('TEST_NA', subdir, testname, str(detail))
        except Exception, detail:
            info = str(detail) + "\n" + traceback.format_exc()
            self.record('FAIL', subdir, testname, info)


    def run_group(self, function, *args, **dargs):
        """\
        function:
                subroutine to run
        *args:
                arguments for the function
        """

        result = None
        name = function.__name__

        # Allow the tag for the group to be specified.
        if dargs.has_key('tag'):
            tag = dargs['tag']
            del dargs['tag']
            if tag:
                name = tag

        old_record_prefix = self.record_prefix
        try:
            try:
                self.record('START', None, name)
                self.record_prefix += '\t'
                result = function(*args, **dargs)
            except Exception, e:
                self.record_prefix = old_record_prefix
                err_msg = str(e) + '\n'
                err_msg += traceback.format_exc()
                self.record('END FAIL', None, name, err_msg)
            else:
                self.record_prefix = old_record_prefix
                self.record('END GOOD', None, name)

        # We don't want to raise up an error higher if it's just
        # a TestError - we want to carry on to other tests. Hence
        # this outer try/except block.
        except error.TestError:
            pass
        except:
            raise error.TestError(name + ' failed\n' +
                                  traceback.format_exc())

        return result


    def run_reboot(self, reboot_func, get_kernel_func):
        """\
        A specialization of run_group meant specifically for handling
        a reboot. Includes support for capturing the kernel version
        after the reboot.

        reboot_func: a function that carries out the reboot

        get_kernel_func: a function that returns a string
        representing the kernel version.
        """

        old_record_prefix = self.record_prefix
        try:
            self.record('START', None, 'reboot')
            self.record_prefix += '\t'
            reboot_func()
        except Exception, e:
            self.record_prefix = old_record_prefix
            err_msg = str(e) + '\n' + traceback.format_exc()
            self.record('END FAIL', None, 'reboot', err_msg)
        else:
            kernel = get_kernel_func()
            self.record_prefix = old_record_prefix
            self.record('END GOOD', None, 'reboot',
                        optional_fields={"kernel": kernel})


    def record(self, status_code, subdir, operation, status='',
               optional_fields=None):
        """
        Record job-level status

        The intent is to make this file both machine parseable and
        human readable. That involves a little more complexity, but
        really isn't all that bad ;-)

        Format is <status code>\t<subdir>\t<operation>\t<status>

        status code: see common_lib.logging.is_valid_status()
                     for valid status definition

        subdir: MUST be a relevant subdirectory in the results,
        or None, which will be represented as '----'

        operation: description of what you ran (e.g. "dbench", or
                                        "mkfs -t foobar /dev/sda9")

        status: error message or "completed sucessfully"

        ------------------------------------------------------------

        Initial tabs indicate indent levels for grouping, and is
        governed by self.record_prefix

        multiline messages have secondary lines prefaced by a double
        space ('  ')

        Executing this method will trigger the logging of all new
        warnings to date from the various console loggers.
        """
        # poll all our warning loggers for new warnings
        warnings = self._read_warnings()
        for timestamp, msg in warnings:
            self._record("WARN", None, None, msg, timestamp)

        # write out the actual status log line
        self._record(status_code, subdir, operation, status,
                      optional_fields=optional_fields)


    def _read_warnings(self):
        warnings = []
        while True:
            # pull in a line of output from every logger that has
            # output ready to be read
            loggers, _, _ = select.select(self.warning_loggers,
                                          [], [], 0)
            closed_loggers = set()
            for logger in loggers:
                line = logger.readline()
                # record any broken pipes (aka line == empty)
                if len(line) == 0:
                    closed_loggers.add(logger)
                    continue
                timestamp, msg = line.split('\t', 1)
                warnings.append((int(timestamp), msg.strip()))

            # stop listening to loggers that are closed
            self.warning_loggers -= closed_loggers

            # stop if none of the loggers have any output left
            if not loggers:
                break

        # sort into timestamp order
        warnings.sort()
        return warnings


    def _render_record(self, status_code, subdir, operation, status='',
                       epoch_time=None, record_prefix=None,
                       optional_fields=None):
        """
        Internal Function to generate a record to be written into a
        status log. For use by server_job.* classes only.
        """
        if subdir:
            if re.match(r'[\n\t]', subdir):
                raise ValueError(
                    'Invalid character in subdir string')
            substr = subdir
        else:
            substr = '----'

        if not logging.is_valid_status(status_code):
            raise ValueError('Invalid status code supplied: %s' %
                             status_code)
        if not operation:
            operation = '----'
        if re.match(r'[\n\t]', operation):
            raise ValueError(
                'Invalid character in operation string')
        operation = operation.rstrip()
        status = status.rstrip()
        status = re.sub(r"\t", "  ", status)
        # Ensure any continuation lines are marked so we can
        # detect them in the status file to ensure it is parsable.
        status = re.sub(r"\n", "\n" + self.record_prefix + "  ", status)

        if not optional_fields:
            optional_fields = {}

        # Generate timestamps for inclusion in the logs
        if epoch_time is None:
            epoch_time = int(time.time())
        local_time = time.localtime(epoch_time)
        optional_fields["timestamp"] = str(epoch_time)
        optional_fields["localtime"] = time.strftime("%b %d %H:%M:%S",
                                                     local_time)

        fields = [status_code, substr, operation]
        fields += ["%s=%s" % x for x in optional_fields.iteritems()]
        fields.append(status)

        if record_prefix is None:
            record_prefix = self.record_prefix

        msg = '\t'.join(str(x) for x in fields)

        return record_prefix + msg + '\n'


    def _record_prerendered(self, msg):
        """
        Record a pre-rendered msg into the status logs. The only
        change this makes to the message is to add on the local
        indentation. Should not be called outside of server_job.*
        classes. Unlike _record, this does not write the message
        to standard output.
        """
        lines = []
        status_file = os.path.join(self.resultdir, 'status.log')
        status_log = open(status_file, 'a')
        for line in msg.splitlines():
            line = self.record_prefix + line + '\n'
            lines.append(line)
            status_log.write(line)
        status_log.close()
        self.__parse_status(lines)


    def _execute_code(self, code, global_scope, local_scope):
        exec(code, global_scope, local_scope)


    def _record(self, status_code, subdir, operation, status='',
                 epoch_time=None, optional_fields=None):
        """
        Actual function for recording a single line into the status
        logs. Should never be called directly, only by job.record as
        this would bypass the console monitor logging.
        """

        msg = self._render_record(status_code, subdir, operation,
                                  status, epoch_time,
                                  optional_fields=optional_fields)


        status_file = os.path.join(self.resultdir, 'status.log')
        sys.stdout.write(msg)
        open(status_file, "a").write(msg)
        if subdir:
            test_dir = os.path.join(self.resultdir, subdir)
            status_file = os.path.join(test_dir, 'status')
            open(status_file, "a").write(msg)
        self.__parse_status(msg.splitlines())


    def __parse_status(self, new_lines):
        if not self.using_parser:
            return
        new_tests = self.parser.process_lines(new_lines)
        for test in new_tests:
            self.__insert_test(test)


    def __insert_test(self, test):
        """ An internal method to insert a new test result into the
        database. This method will not raise an exception, even if an
        error occurs during the insert, to avoid failing a test
        simply because of unexpected database issues."""
        try:
            self.results_db.insert_test(self.job_model, test)
        except Exception:
            msg = ("WARNING: An unexpected error occured while "
                   "inserting test results into the database. "
                   "Ignoring error.\n" + traceback.format_exc())
            print >> sys.stderr, msg
