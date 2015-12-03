"""The main job wrapper

This is the core infrastructure.

Copyright Andy Whitcroft, Martin J. Bligh 2006
"""

import copy
import getpass
import glob
import logging
import os
import re
import shutil
import sys
import time
import traceback
import types
import weakref

from autotest.client import client_logging_config
from autotest.client import config, sysinfo, test, local_host
from autotest.client import partition as partition_lib
from autotest.client import profilers, harness
from autotest.client import utils, parallel, kernel, xen
from autotest.client.shared import base_job, boottool, utils_memory
from autotest.client.shared import base_packages, packages, report
from autotest.client.shared import error, barrier, logging_manager
from autotest.client.shared.settings import settings

LAST_BOOT_TAG = object()
JOB_PREAMBLE = """
from autotest.client.shared.error import *
from autotest.client.utils import *
"""


class StepError(error.AutotestError):
    pass


class NotAvailableError(error.AutotestError):
    pass


def _run_test_complete_on_exit(f):
    """Decorator for job methods that automatically calls
    self.harness.run_test_complete when the method exits, if appropriate."""

    def wrapped(self, *args, **dargs):
        try:
            return f(self, *args, **dargs)
        finally:
            if self._logger.global_filename == 'status':
                self.harness.run_test_complete()
                if self.drop_caches:
                    utils_memory.drop_caches()
    wrapped.__name__ = f.__name__
    wrapped.__doc__ = f.__doc__
    wrapped.__dict__.update(f.__dict__)
    return wrapped


class status_indenter(base_job.status_indenter):

    """Provide a status indenter that is backed by job._record_prefix."""

    def __init__(self, job):
        self.job = weakref.proxy(job)  # avoid a circular reference

    @property
    def indent(self):
        return self.job._record_indent

    def increment(self):
        self.job._record_indent += 1

    def decrement(self):
        self.job._record_indent -= 1


class base_client_job(base_job.base_job):

    """The client-side concrete implementation of base_job.

    Optional properties provided by this implementation:
    - control
    - bootloader
    - harness
    """

    _WARNING_DISABLE_DELAY = 5

    # _record_indent is a persistent property, but only on the client
    _job_state = base_job.base_job._job_state
    _record_indent = _job_state.property_factory(
        '_state', '_record_indent', 0, namespace='client')
    _max_disk_usage_rate = _job_state.property_factory(
        '_state', '_max_disk_usage_rate', 0.0, namespace='client')

    def __init__(self, control, options, drop_caches=True,
                 extra_copy_cmdline=None):
        """
        Prepare a client side job object.

        :param control: The control file (pathname of).
        :param options: an object which includes:
                jobtag: The job tag string (eg "default").
                cont: If this is the continuation of this job.
                harness_type: An alternative server harness.  [None]
                use_external_logging: If true, the enable_external_logging
                          method will be called during construction.  [False]
        :param drop_caches: If true, utils.drop_caches() is called before and
                between all tests.  [True]
        :param extra_copy_cmdline: list of additional /proc/cmdline arguments to
                copy from the running kernel to all the installed kernels with
                this job
        """
        super(base_client_job, self).__init__(options=options)
        self._pre_record_init(control, options)
        try:
            self._post_record_init(control, options, drop_caches,
                                   extra_copy_cmdline)
        except Exception, err:
            self.record(
                'ABORT', None, None, 'client.job.__init__ failed: %s' %
                str(err))
            raise

    @classmethod
    def _get_environ_autodir(cls):
        return os.environ['AUTODIR']

    @classmethod
    # The unittests will hide this method, well, for unittesting
    # pylint: disable=E0202
    def _find_base_directories(cls):
        """
        Determine locations of autodir and clientdir (which are the same)
        using os.environ. Serverdir does not exist in this context.
        """
        autodir = clientdir = cls._get_environ_autodir()
        return autodir, clientdir, None

    @classmethod
    def _parse_args(cls, args):
        return re.findall("[^\s]*?['|\"].*?['|\"]|[^\s]+", args)

    # The unittests will hide this method, well, for unittesting
    # pylint: disable=E0202
    def _find_resultdir(self, options):
        """
        Determine the directory for storing results. On a client this is
        always <autodir>/results/<tag>, where tag is passed in on the command
        line as an option.
        """
        output_dir_config = settings.get_value('CLIENT', 'output_dir',
                                               default="")
        if options.output_dir:
            basedir = options.output_dir
        elif output_dir_config:
            basedir = output_dir_config
        else:
            basedir = self.autodir

        return os.path.join(basedir, 'results', options.tag)

    def _get_status_logger(self):
        """Return a reference to the status logger."""
        return self._logger

    def _pre_record_init(self, control, options):
        """
        Initialization function that should peform ONLY the required
        setup so that the self.record() method works.

        As of now self.record() needs self.resultdir, self._group_level,
        self.harness and of course self._logger.
        """
        if not options.cont:
            self._cleanup_debugdir_files()
            self._cleanup_results_dir()

        logging_manager.configure_logging(
            client_logging_config.ClientLoggingConfig(),
            results_dir=self.resultdir,
            verbose=options.verbose)
        logging.info('Writing results to %s', self.resultdir)

        # init_group_level needs the state
        self.control = os.path.realpath(control)
        self._is_continuation = options.cont
        self._current_step_ancestry = []
        self._next_step_index = 0
        self._load_state()

        _harness = self.handle_persistent_option(options, 'harness')
        _harness_args = self.handle_persistent_option(options, 'harness_args')

        self.harness = harness.select(_harness, self, _harness_args)

        # set up the status logger
        def client_job_record_hook(entry):
            msg_tag = ''
            if '.' in self._logger.global_filename:
                msg_tag = self._logger.global_filename.split('.', 1)[1]
            # send the entry to the job harness
            message = '\n'.join([entry.message] + entry.extra_message_lines)
            rendered_entry = self._logger.render_entry(entry)
            self.harness.test_status_detail(entry.status_code, entry.subdir,
                                            entry.operation, message, msg_tag,
                                            entry.fields)
            self.harness.test_status(rendered_entry, msg_tag)
            # send the entry to stdout, if it's enabled
            logging.info(rendered_entry)
        self._logger = base_job.status_logger(
            self, status_indenter(self), record_hook=client_job_record_hook,
            tap_writer=self._tap)

    def _post_record_init(self, control, options, drop_caches,
                          extra_copy_cmdline):
        """
        Perform job initialization not required by self.record().
        """
        self._init_drop_caches(drop_caches)

        self._init_packages()

        self.sysinfo = sysinfo.sysinfo(self.resultdir)
        self._load_sysinfo_state()

        if not options.cont:
            shutil.copyfile(self.control,
                            os.path.join(self.resultdir, 'control'))

        self.control = control

        self.logging = logging_manager.get_logging_manager(
            manage_stdout_and_stderr=True, redirect_fds=True)
        self.logging.start_logging()

        self._config = config.config(self)
        self.profilers = profilers.profilers(self)

        self._init_bootloader()

        self.machines = [options.hostname]
        self.hosts = set([local_host.LocalHost(hostname=options.hostname,
                                               bootloader=self.bootloader)])

        self.args = []
        if options.args:
            self.args = self._parse_args(options.args)

        if options.user:
            self.user = options.user
        else:
            self.user = getpass.getuser()

        self.sysinfo.log_per_reboot_data()

        if not options.cont:
            self.record('START', None, None)

        self.harness.run_start()

        if options.log:
            self.enable_external_logging()

        self._init_cmdline(extra_copy_cmdline)

        self.num_tests_run = None
        self.num_tests_failed = None

        self.warning_loggers = None
        self.warning_manager = None

    def _init_drop_caches(self, drop_caches):
        """
        Perform the drop caches initialization.
        """
        self.drop_caches_between_iterations = (settings.get_value('CLIENT',
                                                                  'drop_caches_between_iterations',
                                                                  type=bool, default=True))
        self.drop_caches = drop_caches
        if self.drop_caches:
            utils_memory.drop_caches()

    def _init_bootloader(self):
        """
        Perform boottool initialization.
        """
        tool = self.config_get('boottool.executable')
        self.bootloader = boottool.boottool(tool)

    def _init_packages(self):
        """
        Perform the packages support initialization.
        """
        tmpdir = settings.get_value('COMMON', 'test_output_dir',
                                    default=self.autodir)
        self.pkgmgr = packages.PackageManager(
            tmpdir, run_function_dargs={'timeout': 3600})

    def _init_cmdline(self, extra_copy_cmdline):
        """
        Initialize default cmdline for booted kernels in this job.
        """
        copy_cmdline = set(['console'])
        if extra_copy_cmdline is not None:
            copy_cmdline.update(extra_copy_cmdline)

        # extract console= and other args from cmdline and add them into the
        # base args that we use for all kernels we install
        cmdline = utils.read_one_line('/proc/cmdline')
        kernel_args = []
        for karg in cmdline.split():
            for param in copy_cmdline:
                if karg.startswith(param) and \
                        (len(param) == len(karg) or karg[len(param)] == '='):
                    kernel_args.append(karg)
        self.config_set('boot.default_args', ' '.join(kernel_args))

    def _cleanup_results_dir(self):
        """Delete everything in resultsdir"""
        assert os.path.exists(self.resultdir)
        utils.safe_rmdir(self.resultdir)
        os.mkdir(self.resultdir)

    def _cleanup_debugdir_files(self):
        """
        Delete any leftover debugdir files
        """
        list_files = glob.glob("/tmp/autotest_results_dir.*")
        for f in list_files:
            os.remove(f)

    def disable_warnings(self, warning_type):
        self.record("INFO", None, None,
                    "disabling %s warnings" % warning_type,
                    {"warnings.disable": warning_type})
        time.sleep(self._WARNING_DISABLE_DELAY)

    def enable_warnings(self, warning_type):
        time.sleep(self._WARNING_DISABLE_DELAY)
        self.record("INFO", None, None,
                    "enabling %s warnings" % warning_type,
                    {"warnings.enable": warning_type})

    def monitor_disk_usage(self, max_rate):
        """
        Signal that the job should monitor disk space usage on /
        and generate a warning if a test uses up disk space at a
        rate exceeding 'max_rate'.

        Parameters:
             max_rate - the maximium allowed rate of disk consumption
                        during a test, in MB/hour, or 0 to indicate
                        no limit.
        """
        self._max_disk_usage_rate = max_rate

    def relative_path(self, path):
        """
        Return a patch relative to the job results directory
        """
        head = len(self.resultdir) + 1     # remove the / between
        return path[head:]

    def control_get(self):
        return self.control

    def control_set(self, control):
        self.control = os.path.abspath(control)

    def harness_select(self, which, harness_args):
        self.harness = harness.select(which, self, harness_args)

    def config_set(self, name, value):
        self._config.set(name, value)

    def config_get(self, name):
        return self._config.get(name)

    def setup_dirs(self, results_dir, tmp_dir):
        if not tmp_dir:
            tmp_dir = os.path.join(self.tmpdir, 'build')
        if not os.path.exists(tmp_dir):
            os.mkdir(tmp_dir)
        if not os.path.isdir(tmp_dir):
            e_msg = "Temp dir (%s) is not a dir - args backwards?" % self.tmpdir
            raise ValueError(e_msg)

        # We label the first build "build" and then subsequent ones
        # as "build.2", "build.3", etc. Whilst this is a little bit
        # inconsistent, 99.9% of jobs will only have one build
        # (that's not done as kernbench, sparse, or buildtest),
        # so it works out much cleaner. One of life's comprimises.
        if not results_dir:
            results_dir = os.path.join(self.resultdir, 'build')
            i = 2
            while os.path.exists(results_dir):
                results_dir = os.path.join(self.resultdir, 'build.%d' % i)
                i += 1
        if not os.path.exists(results_dir):
            os.mkdir(results_dir)

        return (results_dir, tmp_dir)

    def xen(self, base_tree, results_dir='', tmp_dir='', leave=False,
            kjob=None):
        """Summon a xen object"""
        (results_dir, tmp_dir) = self.setup_dirs(results_dir, tmp_dir)
        build_dir = 'xen'
        return xen.xen(self, base_tree, results_dir, tmp_dir, build_dir,
                       leave, kjob)

    def kernel(self, base_tree, results_dir='', tmp_dir='', leave=False):
        """Summon a kernel object"""
        (results_dir, tmp_dir) = self.setup_dirs(results_dir, tmp_dir)
        build_dir = 'linux'
        return kernel.auto_kernel(self, base_tree, results_dir, tmp_dir,
                                  build_dir, leave)

    def barrier(self, *args, **kwds):
        """Create a barrier object"""
        return barrier.barrier(*args, **kwds)

    def install_pkg(self, name, pkg_type, install_dir):
        '''
        This method is a simple wrapper around the actual package
        installation method in the Packager class. This is used
        internally by the profilers, deps and tests code.

        :param name: name of the package (ex: sleeptest, dbench etc.)
        :param pkg_type: Type of the package (ex: test, dep etc.)
        :param install_dir: The directory in which the source is actually
        untarred into. (ex: client/profilers/<name> for profilers)
        '''
        if self.pkgmgr.repositories:
            self.pkgmgr.install_pkg(name, pkg_type, self.pkgdir, install_dir)

    def add_repository(self, repo_urls):
        '''
        Adds the repository locations to the job so that packages
        can be fetched from them when needed. The repository list
        needs to be a string list
        Ex: job.add_repository(['http://blah1','http://blah2'])
        '''
        for repo_url in repo_urls:
            self.pkgmgr.add_repository(repo_url)

        # Fetch the packages' checksum file that contains the checksums
        # of all the packages if it is not already fetched. The checksum
        # is always fetched whenever a job is first started. This
        # is not done in the job's constructor as we don't have the list of
        # the repositories there (and obviously don't care about this file
        # if we are not using the repos)
        try:
            checksum_file_path = os.path.join(self.pkgmgr.pkgmgr_dir,
                                              base_packages.CHECKSUM_FILE)
            self.pkgmgr.fetch_pkg(base_packages.CHECKSUM_FILE,
                                  checksum_file_path, use_checksum=False)
        except error.PackageFetchError:
            # packaging system might not be working in this case
            # Silently fall back to the normal case
            pass

    def require_gcc(self):
        """
        Test whether gcc is installed on the machine.
        """
        # check if gcc is installed on the system.
        try:
            utils.system('which gcc')
        except error.CmdError:
            raise NotAvailableError('gcc is required by this job and is '
                                    'not available on the system')

    def setup_dep(self, deps):
        """Set up the dependencies for this test.
        deps is a list of libraries required for this test.
        """
        # Fetch the deps from the repositories and set them up.
        for dep in deps:
            dep_dir = os.path.join(self.autodir, 'deps', dep)
            # Search for the dependency in the repositories if specified,
            # else check locally.
            try:
                self.install_pkg(dep, 'dep', dep_dir)
            except error.PackageInstallError:
                # see if the dep is there locally
                pass

            # dep_dir might not exist if it is not fetched from the repos
            if not os.path.exists(dep_dir):
                raise error.TestError("Dependency %s does not exist" % dep)

            os.chdir(dep_dir)
            if execfile('%s.py' % dep, {}) is None:
                logging.info('Dependency %s successfully built', dep)

    def _runtest(self, url, tag, timeout, args, dargs):
        try:
            pid = parallel.fork_start(self.resultdir,
                                      lambda: test.runtest(self, url, tag,
                                                           args, dargs))

            if timeout:
                logging.debug('Waiting for pid %d for %d seconds', pid, timeout)
                parallel.fork_waitfor_timed(self.resultdir, pid, timeout)
            else:
                parallel.fork_waitfor(self.resultdir, pid)

        except error.TestBaseException:
            # These are already classified with an error type (exit_status)
            raise
        except error.JobError:
            raise  # Caught further up and turned into an ABORT.
        except Exception, e:
            # Converts all other exceptions thrown by the test regardless
            # of phase into a TestError(TestBaseException) subclass that
            # reports them with their full stack trace.
            raise error.UnhandledTestError(e)

    def _run_test_base(self, url, *args, **dargs):
        """
        Prepares arguments and run functions to run_test and run_test_detail.

        :param url A url that identifies the test to run.
        :param tag An optional keyword argument that will be added to the
            test and subdir name.
        :param subdir_tag An optional keyword argument that will be added
            to the subdir name.

        :return:
                subdir: Test subdirectory
                testname: Test name
                group_func: Actual test run function
                timeout: Test timeout
        """
        testname = self.pkgmgr.get_package_name(url, 'test')[1]
        testname, subdir, tag = self._build_tagged_test_name(testname, dargs)
        self._make_test_outputdir(subdir)

        timeout = dargs.pop('timeout', None)
        if timeout:
            logging.debug('Test has timeout: %d sec.', timeout)

        def log_warning(reason):
            self.record("WARN", subdir, testname, reason)

        @disk_usage_monitor.watch(log_warning, "/", self._max_disk_usage_rate)
        def group_func():
            try:
                self._runtest(url, tag, timeout, args, dargs)
            except error.TestBaseException, detail:
                # The error is already classified, record it properly.
                self.record(detail.exit_status, subdir, testname, str(detail))
                raise
            else:
                self.record('GOOD', subdir, testname, 'completed successfully')

        return (subdir, testname, group_func, timeout)

    @_run_test_complete_on_exit
    def run_test(self, url, *args, **dargs):
        """
        Summon a test object and run it.

        :param url A url that identifies the test to run.
        :param tag An optional keyword argument that will be added to the
        test and subdir name.
        :param subdir_tag An optional keyword argument that will be added
        to the subdir name.

        :return: True if the test passes, False otherwise.
        """
        (subdir, testname, group_func, timeout) = self._run_test_base(url,
                                                                      *args,
                                                                      **dargs)
        try:
            self._rungroup(subdir, testname, group_func, timeout)
            return True
        except error.TestBaseException:
            return False
        # Any other exception here will be given to the caller
        #
        # NOTE: The only exception possible from the control file here
        # is error.JobError as _runtest() turns all others into an
        # UnhandledTestError that is caught above.

    @_run_test_complete_on_exit
    def run_test_detail(self, url, *args, **dargs):
        """
        Summon a test object and run it, returning test status.

        :param url A url that identifies the test to run.
        :param tag An optional keyword argument that will be added to the
        test and subdir name.
        :param subdir_tag An optional keyword argument that will be added
        to the subdir name.

        :return: Test status
        :see: client/shared/error.py, exit_status
        """
        (subdir, testname, group_func, timeout) = self._run_test_base(url,
                                                                      *args,
                                                                      **dargs)
        try:
            self._rungroup(subdir, testname, group_func, timeout)
            return 'GOOD'
        except error.TestBaseException, detail:
            return detail.exit_status

    def _rungroup(self, subdir, testname, function, timeout, *args, **dargs):
        """
        :param subdir: name of the group
        :param testname: name of the test to run, or support step
        :function: subroutine to run
        :param args: arguments for the function

        :returns: the result of the passed in function
        """

        try:
            optional_fields = None
            if timeout:
                optional_fields = {'timeout': timeout}
            self.record('START', subdir, testname,
                        optional_fields=optional_fields)

            self._state.set('client', 'unexpected_reboot', (subdir, testname))
            try:
                result = function(*args, **dargs)
                self.record('END GOOD', subdir, testname)
                return result
            except error.TestBaseException, e:
                self.record('END %s' % e.exit_status, subdir, testname)
                raise
            except error.JobError, e:
                self.record('END ABORT', subdir, testname)
                raise
            except Exception, e:
                # This should only ever happen due to a bug in the given
                # function's code.  The common case of being called by
                # run_test() will never reach this.  If a control file called
                # run_group() itself, bugs in its function will be caught
                # here.
                err_msg = str(e) + '\n' + traceback.format_exc()
                self.record('END ERROR', subdir, testname, err_msg)
                raise
        finally:
            self._state.discard('client', 'unexpected_reboot')

    def run_group(self, function, tag=None, **dargs):
        """
        Run a function nested within a group level.

        :param function: Callable to run.
        :param tag: An optional tag name for the group.  If None (default)
        function.__name__ will be used.
        :param dargs: Named arguments for the function.
        """
        if tag:
            name = tag
        else:
            name = function.__name__

        try:
            return self._rungroup(subdir=None, testname=name,
                                  function=function, timeout=None, **dargs)
        except (SystemExit, error.TestBaseException):
            raise
        # If there was a different exception, turn it into a TestError.
        # It will be caught by step_engine or _run_step_fn.
        except Exception, e:
            raise error.UnhandledTestError(e)

    def cpu_count(self):
        return utils.count_cpus()  # use total system count

    def start_reboot(self):
        self.record('START', None, 'reboot')
        self.record('GOOD', None, 'reboot.start')

    def _record_reboot_failure(self, subdir, operation, status,
                               running_id=None):
        self.record("ABORT", subdir, operation, status)
        if not running_id:
            running_id = utils.running_os_ident()
        kernel = {"kernel": running_id.split("::")[0]}
        self.record("END ABORT", subdir, 'reboot', optional_fields=kernel)

    def _check_post_reboot(self, subdir, running_id=None):
        """
        Function to perform post boot checks such as if the system configuration
        has changed across reboots (specifically, CPUs and partitions).

        :param subdir: The subdir to use in the job.record call.
        :param running_id: An optional running_id to include in the reboot
            failure log message

        :raise JobError: Raised if the current configuration does not match the
            pre-reboot configuration.
        """
        abort_on_mismatch = settings.get_value('CLIENT', 'abort_on_mismatch',
                                               type=bool, default=False)
        # check to see if any partitions have changed
        partition_list = partition_lib.get_partition_list(self,
                                                          exclude_swap=False)
        mount_info = partition_lib.get_mount_info(partition_list)
        old_mount_info = self._state.get('client', 'mount_info')
        if mount_info != old_mount_info:
            new_entries = mount_info - old_mount_info
            old_entries = old_mount_info - mount_info
            description = ("mounted partitions are different after reboot "
                           "(old entries: %s, new entries: %s)" %
                           (old_entries, new_entries))
            if abort_on_mismatch:
                self._record_reboot_failure(subdir, "reboot.verify_config",
                                            description, running_id=running_id)
                raise error.JobError("Reboot failed: %s" % description)
            else:
                logging.warning(description)

        # check to see if any CPUs have changed
        cpu_count = utils.count_cpus()
        old_count = self._state.get('client', 'cpu_count')
        if cpu_count != old_count:
            description = ('Number of CPUs changed after reboot '
                           '(old count: %d, new count: %d)' %
                           (old_count, cpu_count))
            if abort_on_mismatch:
                self._record_reboot_failure(subdir, 'reboot.verify_config',
                                            description, running_id=running_id)
                raise error.JobError('Reboot failed: %s' % description)
            else:
                logging.warning(description)

    def end_reboot(self, subdir, kernel, patches, running_id=None):
        self._check_post_reboot(subdir, running_id=running_id)

        # strip ::<timestamp> from the kernel version if present
        kernel = kernel.split("::")[0]
        kernel_info = {"kernel": kernel}
        for i, patch in enumerate(patches):
            kernel_info["patch%d" % i] = patch
        self.record("END GOOD", subdir, "reboot", optional_fields=kernel_info)

    def end_reboot_and_verify(self, expected_when, expected_id, subdir,
                              type='src', patches=[]):
        """ Check the passed kernel identifier against the command line
            and the running kernel, abort the job on missmatch. """

        logging.info("POST BOOT: checking booted kernel "
                     "mark=%d identity='%s' type='%s'",
                     expected_when, expected_id, type)

        running_id = utils.running_os_ident()

        cmdline = utils.read_one_line("/proc/cmdline")

        find_sum = re.compile(r'.*IDENT=(\d+)')
        m = find_sum.match(cmdline)
        cmdline_when = -1
        if m:
            cmdline_when = int(m.groups()[0])

        # We have all the facts, see if they indicate we
        # booted the requested kernel or not.
        bad = False
        if (type == 'src' and expected_id != running_id or
            type == 'rpm' and
                not running_id.startswith(expected_id + '::')):
            logging.error("Kernel identifier mismatch")
            bad = True
        if expected_when != cmdline_when:
            logging.error("Kernel command line mismatch")
            bad = True

        if bad:
            logging.error("   Expected Ident: " + expected_id)
            logging.error("    Running Ident: " + running_id)
            logging.error("    Expected Mark: %d", expected_when)
            logging.error("Command Line Mark: %d", cmdline_when)
            logging.error("     Command Line: " + cmdline)

            self._record_reboot_failure(subdir, "reboot.verify", "boot failure",
                                        running_id=running_id)
            raise error.JobError("Reboot returned with the wrong kernel")

        self.record('GOOD', subdir, 'reboot.verify',
                    utils.running_os_full_version())
        self.end_reboot(subdir, expected_id, patches, running_id=running_id)

    def partition(self, device, loop_size=0, mountpoint=None):
        """
        Work with a machine partition

            :param device: e.g. /dev/sda2, /dev/sdb1 etc...
            :param mountpoint: Specify a directory to mount to. If not specified
                               autotest tmp directory will be used.
            :param loop_size: Size of loopback device (in MB). Defaults to 0.

            :return: A L{client.partition.partition} object
        """

        if not mountpoint:
            mountpoint = self.tmpdir
        return partition_lib.partition(self, device, loop_size, mountpoint)

    @utils.deprecated
    def filesystem(self, device, mountpoint=None, loop_size=0):
        """ Same as partition

        :deprecated: Use partition method instead
        """
        return self.partition(device, loop_size, mountpoint)

    def enable_external_logging(self):
        pass

    def disable_external_logging(self):
        pass

    def reboot_setup(self):
        # save the partition list and mount points, as well as the cpu count
        partition_list = partition_lib.get_partition_list(self,
                                                          exclude_swap=False)
        mount_info = partition_lib.get_mount_info(partition_list)
        self._state.set('client', 'mount_info', mount_info)
        self._state.set('client', 'cpu_count', utils.count_cpus())

    def reboot(self, tag=LAST_BOOT_TAG):
        if tag == LAST_BOOT_TAG:
            tag = self.last_boot_tag
        else:
            self.last_boot_tag = tag

        self.reboot_setup()
        self.harness.run_reboot()
        default = self.config_get('boot.set_default')
        if default:
            self.bootloader.set_default(tag)
        else:
            self.bootloader.boot_once(tag)

        # HACK: using this as a module sometimes hangs shutdown, so if it's
        # installed unload it first
        utils.system("modprobe -r netconsole", ignore_status=True)

        # sync first, so that a sync during shutdown doesn't time out
        utils.system("sync; sync", ignore_status=True)

        sleep_before_reboot = settings.get_value('CLIENT', 'sleep_before_reboot',
                                                 default="5")

        sleep_cmd = "(sleep %s; reboot) </dev/null >/dev/null 2>&1 &" % sleep_before_reboot
        utils.system(sleep_cmd)

        self.quit()

    def noop(self, text):
        logging.info("job: noop: " + text)

    @_run_test_complete_on_exit
    def parallel(self, *tasklist):
        """Run tasks in parallel"""

        pids = []
        old_log_filename = self._logger.global_filename
        for i, task in enumerate(tasklist):
            assert isinstance(task, (tuple, list))
            self._logger.global_filename = old_log_filename + (".%d" % i)

            def task_func():
                # stub out _record_indent with a process-local one
                base_record_indent = self._record_indent
                proc_local = self._job_state.property_factory(
                    '_state', '_record_indent.%d' % os.getpid(),
                    base_record_indent, namespace='client')
                self.__class__._record_indent = proc_local
                task[0](*task[1:])
            pids.append(parallel.fork_start(self.resultdir, task_func))

        old_log_path = os.path.join(self.resultdir, old_log_filename)
        old_log = open(old_log_path, "a")
        exceptions = []
        for i, pid in enumerate(pids):
            # wait for the task to finish
            try:
                parallel.fork_waitfor(self.resultdir, pid)
            except Exception, e:
                exceptions.append(e)
            # copy the logs from the subtask into the main log
            new_log_path = old_log_path + (".%d" % i)
            if os.path.exists(new_log_path):
                new_log = open(new_log_path)
                old_log.write(new_log.read())
                new_log.close()
                old_log.flush()
                os.remove(new_log_path)
        old_log.close()

        self._logger.global_filename = old_log_filename

        # handle any exceptions raised by the parallel tasks
        if exceptions:
            msg = "%d task(s) failed in job.parallel" % len(exceptions)
            raise error.JobError(msg)

    def quit(self):
        # XXX: should have a better name.
        self.harness.run_pause()
        raise error.JobContinue("more to come")

    def complete(self, status):
        """Write pending TAP reports, clean up, and exit"""
        # write out TAP reports
        if self._tap.do_tap_report:
            self._tap.write()
            self._tap._write_tap_archive()

        # write out a job HTML report
        try:
            report.write_html_report(self.resultdir)
        except Exception, e:
            logging.error("Error writing job HTML report: %s", e)

        # We are about to exit 'complete' so clean up the control file.
        dest = os.path.join(self.resultdir, os.path.basename(self._state_file))
        shutil.move(self._state_file, dest)

        self.harness.run_complete()
        self.disable_external_logging()
        sys.exit(status)

    def _load_state(self):
        autodir = os.path.abspath(os.environ['AUTODIR'])
        tmpdir = os.path.join(autodir, 'tmp')
        state_config = settings.get_value('COMMON', 'test_output_dir',
                                          default=tmpdir)
        if not os.path.isdir(state_config):
            os.makedirs(state_config)
        init_state_file = os.path.join(state_config,
                                       ("%s.init.state" %
                                        os.path.basename(self.control)))
        self._state_file = os.path.join(state_config,
                                        ("%s.state" %
                                         os.path.basename(self.control)))

        if os.path.exists(init_state_file):
            shutil.move(init_state_file, self._state_file)
        self._state.set_backing_file(self._state_file)

        # initialize the state engine, if necessary
        has_steps = self._state.has('client', 'steps')
        if not self._is_continuation and has_steps:
            raise RuntimeError('Loaded state can only contain client.steps if '
                               'this is a continuation')

        if not has_steps:
            logging.debug('Initializing the state engine')
            self._state.set('client', 'steps', [])

    def handle_persistent_option(self, options, option_name):
        """
        Select option from command line or persistent state.
        Store selected option to allow standalone client to continue
        after reboot with previously selected options.
        Priority:
        1. explicitly specified via command line
        2. stored in state file (if continuing job '-c')
        3. default is None
        """
        option = None
        cmd_line_option = getattr(options, option_name)
        if cmd_line_option:
            option = cmd_line_option
            self._state.set('client', option_name, option)
        else:
            stored_option = self._state.get('client', option_name, None)
            if stored_option:
                option = stored_option
        logging.debug('Persistent option %s now set to %s', option_name, option)
        return option

    def __create_step_tuple(self, fn, args, dargs):
        # Legacy code passes in an array where the first arg is
        # the function or its name.
        if isinstance(fn, list):
            assert(len(args) == 0)
            assert(len(dargs) == 0)
            args = fn[1:]
            fn = fn[0]
        # Pickling actual functions is hairy, thus we have to call
        # them by name.  Unfortunately, this means only functions
        # defined globally can be used as a next step.
        if callable(fn):
            fn = fn.__name__
        if not isinstance(fn, types.StringTypes):
            raise StepError("Next steps must be functions or "
                            "strings containing the function name")
        ancestry = copy.copy(self._current_step_ancestry)
        return (ancestry, fn, args, dargs)

    def next_step_append(self, fn, *args, **dargs):
        """Define the next step and place it at the end"""
        steps = self._state.get('client', 'steps')
        steps.append(self.__create_step_tuple(fn, args, dargs))
        self._state.set('client', 'steps', steps)

    def next_step(self, fn, *args, **dargs):
        """Create a new step and place it after any steps added
        while running the current step but before any steps added in
        previous steps"""
        steps = self._state.get('client', 'steps')
        steps.insert(self._next_step_index,
                     self.__create_step_tuple(fn, args, dargs))
        self._next_step_index += 1
        self._state.set('client', 'steps', steps)

    def next_step_prepend(self, fn, *args, **dargs):
        """Insert a new step, executing first"""
        steps = self._state.get('client', 'steps')
        steps.insert(0, self.__create_step_tuple(fn, args, dargs))
        self._next_step_index += 1
        self._state.set('client', 'steps', steps)

    def _run_step_fn(self, local_vars, fn, args, dargs):
        """Run a (step) function within the given context"""

        local_vars['__args'] = args
        local_vars['__dargs'] = dargs
        try:
            exec('__ret = %s(*__args, **__dargs)' % fn, local_vars, local_vars)
            return local_vars['__ret']
        except SystemExit:
            raise  # Send error.JobContinue and JobComplete on up to runjob.
        except error.TestNAError, detail:
            self.record(detail.exit_status, None, fn, str(detail))
        except Exception, detail:
            raise error.UnhandledJobError(detail)

    def _create_frame(self, global_vars, ancestry, fn_name):
        """Set up the environment like it would have been when this
        function was first defined.

        Child step engine 'implementations' must have 'return locals()'
        at end end of their steps.  Because of this, we can call the
        parent function and get back all child functions (i.e. those
        defined within it).

        Unfortunately, the call stack of the function calling
        job.next_step might have been deeper than the function it
        added.  In order to make sure that the environment is what it
        should be, we need to then pop off the frames we built until
        we find the frame where the function was first defined."""

        # The copies ensure that the parent frames are not modified
        # while building child frames.  This matters if we then
        # pop some frames in the next part of this function.
        current_frame = copy.copy(global_vars)
        frames = [current_frame]
        for steps_fn_name in ancestry:
            ret = self._run_step_fn(current_frame, steps_fn_name, [], {})
            current_frame = copy.copy(ret)
            frames.append(current_frame)

        # Walk up the stack frames until we find the place fn_name was defined.
        while len(frames) > 2:
            if fn_name not in frames[-2]:
                break
            if frames[-2][fn_name] != frames[-1][fn_name]:
                break
            frames.pop()
            ancestry.pop()

        return (frames[-1], ancestry)

    def _add_step_init(self, local_vars, current_function):
        """If the function returned a dictionary that includes a
        function named 'step_init', prepend it to our list of steps.
        This will only get run the first time a function with a nested
        use of the step engine is run."""

        if (isinstance(local_vars, dict) and
            'step_init' in local_vars and
                callable(local_vars['step_init'])):
            # The init step is a child of the function
            # we were just running.
            self._current_step_ancestry.append(current_function)
            self.next_step_prepend('step_init')

    def step_engine(self):
        """The multi-run engine used when the control file defines step_init.

        Does the next step.
        """

        # Set up the environment and then interpret the control file.
        # Some control files will have code outside of functions,
        # which means we need to have our state engine initialized
        # before reading in the file.
        global_control_vars = {'job': self,
                               'args': self.args}
        exec(JOB_PREAMBLE, global_control_vars, global_control_vars)
        try:
            execfile(self.control, global_control_vars, global_control_vars)
        except error.TestNAError, detail:
            self.record(detail.exit_status, None, self.control, str(detail))
        except SystemExit:
            raise  # Send error.JobContinue and JobComplete on up to runjob.
        except Exception, detail:
            # Syntax errors or other general Python exceptions coming out of
            # the top level of the control file itself go through here.
            raise error.UnhandledJobError(detail)

        # If we loaded in a mid-job state file, then we presumably
        # know what steps we have yet to run.
        if not self._is_continuation:
            if 'step_init' in global_control_vars:
                self.next_step(global_control_vars['step_init'])
        else:
            # if last job failed due to unexpected reboot, record it as fail
            # so harness gets called
            last_job = self._state.get('client', 'unexpected_reboot', None)
            if last_job:
                subdir, testname = last_job
                self.record('FAIL', subdir, testname, 'unexpected reboot')
                self.record('END FAIL', subdir, testname)

        # Iterate through the steps.  If we reboot, we'll simply
        # continue iterating on the next step.
        while len(self._state.get('client', 'steps')) > 0:
            steps = self._state.get('client', 'steps')
            (ancestry, fn_name, args, dargs) = steps.pop(0)
            self._state.set('client', 'steps', steps)

            self._next_step_index = 0
            ret = self._create_frame(global_control_vars, ancestry, fn_name)
            local_vars, self._current_step_ancestry = ret
            local_vars = self._run_step_fn(local_vars, fn_name, args, dargs)
            self._add_step_init(local_vars, fn_name)

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
        self._save_sysinfo_state()

    def _load_sysinfo_state(self):
        state = self._state.get('client', 'sysinfo', None)
        if state:
            self.sysinfo.deserialize(state)

    def _save_sysinfo_state(self):
        state = self.sysinfo.serialize()
        self._state.set('client', 'sysinfo', state)


class disk_usage_monitor:

    def __init__(self, logging_func, device, max_mb_per_hour):
        self.func = logging_func
        self.device = device
        self.max_mb_per_hour = max_mb_per_hour

    def start(self):
        self.initial_space = utils.freespace(self.device)
        self.start_time = time.time()

    def stop(self):
        # if no maximum usage rate was set, we don't need to
        # generate any warnings
        if not self.max_mb_per_hour:
            return

        final_space = utils.freespace(self.device)
        used_space = self.initial_space - final_space
        stop_time = time.time()
        total_time = stop_time - self.start_time
        # round up the time to one minute, to keep extremely short
        # tests from generating false positives due to short, badly
        # timed bursts of activity
        total_time = max(total_time, 60.0)

        # determine the usage rate
        bytes_per_sec = used_space / total_time
        mb_per_sec = bytes_per_sec / 1024 ** 2
        mb_per_hour = mb_per_sec * 60 * 60

        if mb_per_hour > self.max_mb_per_hour:
            msg = ("disk space on %s was consumed at a rate of %.2f MB/hour")
            msg %= (self.device, mb_per_hour)
            self.func(msg)

    @classmethod
    def watch(cls, *monitor_args, **monitor_dargs):
        """ Generic decorator to wrap a function call with the
        standard create-monitor -> start -> call -> stop idiom."""
        def decorator(func):
            def watched_func(*args, **dargs):
                monitor = cls(*monitor_args, **monitor_dargs)
                monitor.start()
                try:
                    func(*args, **dargs)
                finally:
                    monitor.stop()
            return watched_func
        return decorator


def runjob(control, drop_caches, options):
    """
    Run a job using the given control file.

    This is the main interface to this module.

    :see: base_job.__init__ for parameter info.
    """
    control = os.path.abspath(control)

    try:
        autodir = os.path.abspath(os.environ['AUTODIR'])
    except KeyError:
        autodir = settings.get_value('COMMON', 'autotest_top_path')

    tmpdir = os.path.join(autodir, 'tmp')
    tests_out_dir = settings.get_value('COMMON', 'test_output_dir',
                                       default=tmpdir)
    state = os.path.join(tests_out_dir, os.path.basename(control) + '.state')

    # Ensure state file is cleaned up before the job starts to run if autotest
    # is not running with the --continue flag
    if not options.cont and os.path.isfile(state):
        os.remove(state)

    # instantiate the job object ready for the control file.
    myjob = None
    try:
        # Check that the control file is valid
        if not os.path.exists(control):
            raise error.JobError(control + ": control file not found")

        # When continuing, the job is complete when there is no
        # state file, ensure we don't try and continue.
        if options.cont and not os.path.exists(state):
            raise error.JobComplete("all done")

        myjob = job(control=control, drop_caches=drop_caches, options=options)

        # Load in the users control file, may do any one of:
        #  1) execute in toto
        #  2) define steps, and select the first via next_step()
        myjob.step_engine()

    except error.JobContinue:
        sys.exit(5)

    except error.JobComplete:
        sys.exit(1)

    except error.JobError, instance:
        logging.error("JOB ERROR: " + str(instance))
        if myjob:
            command = None
            if len(instance.args) > 1:
                command = instance.args[1]
                myjob.record('ABORT', None, command, str(instance))
            myjob.record('END ABORT', None, None, str(instance))
            assert myjob._record_indent == 0
            myjob.complete(1)
        else:
            sys.exit(1)

    except Exception, e:
        # NOTE: job._run_step_fn and job.step_engine will turn things into
        # a JobError for us.  If we get here, its likely an autotest bug.
        msg = str(e) + '\n' + traceback.format_exc()
        logging.critical("JOB ERROR (autotest bug?): " + msg)
        if myjob:
            myjob.record('END ABORT', None, None, msg)
            assert myjob._record_indent == 0
            myjob.complete(1)
        else:
            sys.exit(1)

    # If we get here, then we assume the job is complete and good.
    myjob.record('END GOOD', None, None)
    assert myjob._record_indent == 0

    myjob.complete(0)


site_job = utils.import_site_class(
    __file__, "autotest.client.site_job", "site_job", base_client_job)


class job(site_job):
    pass
