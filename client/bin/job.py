"""The main job wrapper

This is the core infrastructure.

Copyright Andy Whitcroft, Martin J. Bligh 2006
"""

import copy, os, platform, re, shutil, sys, time, traceback, types, glob
import logging
import cPickle as pickle
from autotest_lib.client.bin import client_logging_config
from autotest_lib.client.bin import utils, parallel, kernel, xen
from autotest_lib.client.bin import profilers, boottool, harness
from autotest_lib.client.bin import config, sysinfo, test, local_host
from autotest_lib.client.bin import partition as partition_lib
from autotest_lib.client.common_lib import error, barrier, log, logging_manager
from autotest_lib.client.common_lib import base_packages, packages

LAST_BOOT_TAG = object()
NO_DEFAULT = object()
JOB_PREAMBLE = """
from autotest_lib.client.common_lib.error import *
from autotest_lib.client.bin.utils import *
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
            if self.log_filename == self.DEFAULT_LOG_FILENAME:
                self.harness.run_test_complete()
                if self.drop_caches:
                    logging.debug("Dropping caches")
                    utils.drop_caches()
    wrapped.__name__ = f.__name__
    wrapped.__doc__ = f.__doc__
    wrapped.__dict__.update(f.__dict__)
    return wrapped


class base_job(object):
    """The actual job against which we do everything.

    Properties:
            autodir
                    The top level autotest directory (/usr/local/autotest).
                    Comes from os.environ['AUTODIR'].
            bindir
                    <autodir>/bin/
            libdir
                    <autodir>/lib/
            testdir
                    <autodir>/tests/
            configdir
                    <autodir>/config/
            site_testdir
                    <autodir>/site_tests/
            profdir
                    <autodir>/profilers/
            tmpdir
                    <autodir>/tmp/
            pkgdir
                    <autodir>/packages/
            resultdir
                    <autodir>/results/<jobtag>
            toolsdir
                    <autodir>/tools/
            logging
                    logging_manager.LoggingManager object
            profilers
                    the profilers object for this job
            harness
                    the server harness object for this job
            config
                    the job configuration for this job
            drop_caches_between_iterations
                    drop the pagecache between each iteration
    """

    DEFAULT_LOG_FILENAME = "status"
    WARNING_DISABLE_DELAY = 5

    def __init__(self, control, options, drop_caches=True,
                 extra_copy_cmdline=None):
        """
        Prepare a client side job object.

        @param control: The control file (pathname of).
        @param options: an object which includes:
                jobtag: The job tag string (eg "default").
                cont: If this is the continuation of this job.
                harness_type: An alternative server harness.  [None]
                use_external_logging: If true, the enable_external_logging
                          method will be called during construction.  [False]
        @param drop_caches: If true, utils.drop_caches() is called before and
                between all tests.  [True]
        @param extra_copy_cmdline: list of additional /proc/cmdline arguments to
                copy from the running kernel to all the installed kernels with
                this job
        """
        self._pre_record_init(control, options)
        try:
            self._post_record_init(control, options, drop_caches,
                                   extra_copy_cmdline)
        except Exception, err:
            self.record(
                    'ABORT', None, None,'client.bin.job.__init__ failed: %s' %
                    str(err))
            raise


    def _pre_record_init(self, control, options):
        """
        Initialization function that should peform ONLY the required
        setup so that the self.record() method works.

        As of now self.record() needs self.resultdir, self.group_level,
        self.log_filename, self.harness.
        """
        self.autodir = os.environ['AUTODIR']
        self.resultdir = os.path.join(self.autodir, 'results', options.tag)
        self.tmpdir = os.path.join(self.autodir, 'tmp')

        if not os.path.exists(self.resultdir):
            os.makedirs(self.resultdir)

        if not options.cont:
            self._cleanup_results_dir()
            # Don't cleanup the tmp dir (which contains the lockfile)
            # in the constructor, this would be a problem for multiple
            # jobs starting at the same time on the same client. Instead
            # do the delete at the server side. We simply create the tmp
            # directory here if it does not already exist.
            if not os.path.exists(self.tmpdir):
                os.mkdir(self.tmpdir)

        logging_manager.configure_logging(
                client_logging_config.ClientLoggingConfig(),
                results_dir=self.resultdir,
                verbose=options.verbose)
        logging.info('Writing results to %s', self.resultdir)

        self.log_filename = self.DEFAULT_LOG_FILENAME

        # init_group_level needs the state
        self.control = os.path.realpath(control)
        self._is_continuation = options.cont
        self.state_file = self.control + '.state'
        self.current_step_ancestry = []
        self.next_step_index = 0
        self.testtag = ''
        self._test_tag_prefix = ''
        self._load_state()

        self._init_group_level()

        self.harness = harness.select(options.harness, self)


    def _post_record_init(self, control, options, drop_caches,
                          extra_copy_cmdline):
        """
        Perform job initialization not required by self.record().
        """
        self.bindir = os.path.join(self.autodir, 'bin')
        self.libdir = os.path.join(self.autodir, 'lib')
        self.testdir = os.path.join(self.autodir, 'tests')
        self.configdir = os.path.join(self.autodir, 'config')
        self.site_testdir = os.path.join(self.autodir, 'site_tests')
        self.profdir = os.path.join(self.autodir, 'profilers')
        self.toolsdir = os.path.join(self.autodir, 'tools')

        self._init_drop_caches(drop_caches)

        self._init_packages()
        self.run_test_cleanup = self.get_state("__run_test_cleanup",
                                                default=True)

        self.sysinfo = sysinfo.sysinfo(self.resultdir)
        self._load_sysinfo_state()

        self.last_boot_tag = self.get_state("__last_boot_tag", default=None)
        self.tag = self.get_state("__job_tag", default=None)

        if not options.cont:
            if not os.path.exists(self.pkgdir):
                os.mkdir(self.pkgdir)

            results = os.path.join(self.autodir, 'results')
            if not os.path.exists(results):
                os.mkdir(results)

            download = os.path.join(self.testdir, 'download')
            if not os.path.exists(download):
                os.mkdir(download)

            os.makedirs(os.path.join(self.resultdir, 'analysis'))

            shutil.copyfile(self.control,
                            os.path.join(self.resultdir, 'control'))


        self.control = control
        self.jobtag = options.tag

        self.logging = logging_manager.get_logging_manager(
                manage_stdout_and_stderr=True, redirect_fds=True)
        self.logging.start_logging()

        self.config = config.config(self)
        self.profilers = profilers.profilers(self)
        self.host = local_host.LocalHost(hostname=options.hostname)
        self.autoserv_user = options.autoserv_user

        self._init_bootloader()

        self.sysinfo.log_per_reboot_data()

        if not options.cont:
            self.record('START', None, None)
            self._increment_group_level()

        self.harness.run_start()

        if options.log:
            self.enable_external_logging()

        # load the max disk usage rate - default to no monitoring
        self.max_disk_usage_rate = self.get_state('__monitor_disk', default=0.0)

        self._init_cmdline(extra_copy_cmdline)


    def _init_drop_caches(self, drop_caches):
        """
        Perform the drop caches initialization.
        """
        self.drop_caches_between_iterations = True
        self.drop_caches = drop_caches
        if self.drop_caches:
            logging.debug("Dropping caches")
            utils.drop_caches()


    def _init_bootloader(self):
        """
        Perform boottool initialization.
        """
        try:
            tool = self.config_get('boottool.executable')
            self.bootloader = boottool.boottool(tool)
        except:
            pass


    def _init_packages(self):
        """
        Perform the packages support initialization.
        """
        self.pkgmgr = packages.PackageManager(
            self.autodir, run_function_dargs={'timeout':3600})
        self.pkgdir = os.path.join(self.autodir, 'packages')


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
        list_files = glob.glob('%s/*' % self.resultdir)
        for f in list_files:
            if os.path.isdir(f):
                shutil.rmtree(f)
            elif os.path.isfile(f):
                os.remove(f)


    def disable_warnings(self, warning_type):
        self.record("INFO", None, None,
                    "disabling %s warnings" % warning_type,
                    {"warnings.disable": warning_type})
        time.sleep(self.WARNING_DISABLE_DELAY)


    def enable_warnings(self, warning_type):
        time.sleep(self.WARNING_DISABLE_DELAY)
        self.record("INFO", None, None,
                    "enabling %s warnings" % warning_type,
                    {"warnings.enable": warning_type})


    def monitor_disk_usage(self, max_rate):
        """\
        Signal that the job should monitor disk space usage on /
        and generate a warning if a test uses up disk space at a
        rate exceeding 'max_rate'.

        Parameters:
             max_rate - the maximium allowed rate of disk consumption
                        during a test, in MB/hour, or 0 to indicate
                        no limit.
        """
        self.set_state('__monitor_disk', max_rate)
        self.max_disk_usage_rate = max_rate


    def relative_path(self, path):
        """\
        Return a patch relative to the job results directory
        """
        head = len(self.resultdir) + 1     # remove the / inbetween
        return path[head:]


    def control_get(self):
        return self.control


    def control_set(self, control):
        self.control = os.path.abspath(control)


    def harness_select(self, which):
        self.harness = harness.select(which, self)


    def config_set(self, name, value):
        self.config.set(name, value)


    def config_get(self, name):
        return self.config.get(name)


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


    def xen(self, base_tree, results_dir = '', tmp_dir = '', leave = False, \
                            kjob = None ):
        """Summon a xen object"""
        (results_dir, tmp_dir) = self.setup_dirs(results_dir, tmp_dir)
        build_dir = 'xen'
        return xen.xen(self, base_tree, results_dir, tmp_dir, build_dir,
                       leave, kjob)


    def kernel(self, base_tree, results_dir = '', tmp_dir = '', leave = False):
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
        name : name of the package (ex: sleeptest, dbench etc.)
        pkg_type : Type of the package (ex: test, dep etc.)
        install_dir : The directory in which the source is actually
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
        except error.CmdError, e:
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
            utils.system('./' + dep + '.py')


    def _runtest(self, url, tag, args, dargs):
        try:
            l = lambda : test.runtest(self, url, tag, args, dargs)
            pid = parallel.fork_start(self.resultdir, l)
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


    @_run_test_complete_on_exit
    def run_test(self, url, *args, **dargs):
        """Summon a test object and run it.

        tag
                tag to add to testname
        url
                url of the test to run
        """

        if not url:
            raise TypeError("Test name is invalid. "
                            "Switched arguments?")
        (group, testname) = self.pkgmgr.get_package_name(url, 'test')
        namelen = len(testname)
        dargs = dargs.copy()
        tntag = dargs.pop('tag', None)
        if tntag:         # per-test tag  is included in reported test name
            testname += '.' + str(tntag)
        run_number = self.get_run_number()
        if run_number:
            testname += '._%02d_' % run_number
            self.set_run_number(run_number + 1)
        if self._is_kernel_in_test_tag():
            testname += '.' + platform.release()
        if self._test_tag_prefix:
            testname += '.' + self._test_tag_prefix
        if self.testtag:  # job-level tag is included in reported test name
            testname += '.' + self.testtag
        subdir = testname
        sdtag = dargs.pop('subdir_tag', None)
        if sdtag:  # subdir-only tag is not included in reports
            subdir = subdir + '.' + str(sdtag)
        tag = subdir[namelen+1:]    # '' if none

        outputdir = os.path.join(self.resultdir, subdir)
        if os.path.exists(outputdir):
            msg = ("%s already exists, test <%s> may have"
                    " already run with tag <%s>"
                    % (outputdir, testname, tag) )
            raise error.TestError(msg)
        # NOTE: client/common_lib/test.py runtest() depends directory names
        # being constructed the same way as in this code.
        os.mkdir(outputdir)

        def log_warning(reason):
            self.record("WARN", subdir, testname, reason)
        @disk_usage_monitor.watch(log_warning, "/", self.max_disk_usage_rate)
        def group_func():
            try:
                self._runtest(url, tag, args, dargs)
            except error.TestBaseException, detail:
                # The error is already classified, record it properly.
                self.record(detail.exit_status, subdir, testname, str(detail))
                raise
            else:
                self.record('GOOD', subdir, testname, 'completed successfully')

        try:
            self._rungroup(subdir, testname, group_func)
            return True
        except error.TestBaseException:
            return False
        # Any other exception here will be given to the caller
        #
        # NOTE: The only exception possible from the control file here
        # is error.JobError as _runtest() turns all others into an
        # UnhandledTestError that is caught above.


    def _rungroup(self, subdir, testname, function, *args, **dargs):
        """\
        subdir:
                name of the group
        testname:
                name of the test to run, or support step
        function:
                subroutine to run
        *args:
                arguments for the function

        Returns the result of the passed in function
        """

        try:
            self.record('START', subdir, testname)
            self._increment_group_level()
            result = function(*args, **dargs)
            self._decrement_group_level()
            self.record('END GOOD', subdir, testname)
            return result
        except error.TestBaseException, e:
            self._decrement_group_level()
            self.record('END %s' % e.exit_status, subdir, testname)
            raise
        except error.JobError, e:
            self._decrement_group_level()
            self.record('END ABORT', subdir, testname)
            raise
        except Exception, e:
            # This should only ever happen due to a bug in the given
            # function's code.  The common case of being called by
            # run_test() will never reach this.  If a control file called
            # run_group() itself, bugs in its function will be caught
            # here.
            self._decrement_group_level()
            err_msg = str(e) + '\n' + traceback.format_exc()
            self.record('END ERROR', subdir, testname, err_msg)
            raise


    def run_group(self, function, tag=None, **dargs):
        """
        Run a function nested within a group level.

        function:
                Callable to run.
        tag:
                An optional tag name for the group.  If None (default)
                function.__name__ will be used.
        **dargs:
                Named arguments for the function.
        """
        if tag:
            name = tag
        else:
            name = function.__name__

        try:
            return self._rungroup(subdir=None, testname=name,
                                  function=function, **dargs)
        except (SystemExit, error.TestBaseException):
            raise
        # If there was a different exception, turn it into a TestError.
        # It will be caught by step_engine or _run_step_fn.
        except Exception, e:
            raise error.UnhandledTestError(e)


    _RUN_NUMBER_STATE = '__run_number'
    def get_run_number(self):
        """Get the run number or 0 if no run number has been set."""
        return self.get_state(self._RUN_NUMBER_STATE, default=0)


    def set_run_number(self, number):
        """If the run number is non-zero it will be in the output dir name."""
        self.set_state(self._RUN_NUMBER_STATE, number)


    _KERNEL_IN_TAG_STATE = '__kernel_version_in_test_tag'
    def _is_kernel_in_test_tag(self):
        """Boolean: should the kernel version be included in the test tag."""
        return self.get_state(self._KERNEL_IN_TAG_STATE, default=False)


    def show_kernel_in_test_tag(self, value=True):
        """If True, the kernel version at test time will prefix test tags."""
        self.set_state(self._KERNEL_IN_TAG_STATE, value)


    def set_test_tag(self, tag=''):
        """Set tag to be added to test name of all following run_test steps."""
        self.testtag = tag


    def set_test_tag_prefix(self, prefix):
        """Set a prefix string to prepend to all future run_test steps.

        Args:
          prefix: A string to prepend to any run_test() step tags separated by
              a '.'; use the empty string '' to clear it.
        """
        self._test_tag_prefix = prefix


    def cpu_count(self):
        return utils.count_cpus()  # use total system count


    def start_reboot(self):
        self.record('START', None, 'reboot')
        self._increment_group_level()
        self.record('GOOD', None, 'reboot.start')


    def _record_reboot_failure(self, subdir, operation, status,
                               running_id=None):
        self.record("ABORT", subdir, operation, status)
        self._decrement_group_level()
        if not running_id:
            running_id = utils.running_os_ident()
        kernel = {"kernel": running_id.split("::")[0]}
        self.record("END ABORT", subdir, 'reboot', optional_fields=kernel)


    def _check_post_reboot(self, subdir, running_id=None):
        """
        Function to perform post boot checks such as if the mounted
        partition list has changed across reboots.
        """
        partition_list = partition_lib.get_partition_list(self)
        mount_info = set((p.device, p.get_mountpoint()) for p in partition_list)
        old_mount_info = self.get_state("__mount_info")
        if mount_info != old_mount_info:
            new_entries = mount_info - old_mount_info
            old_entries = old_mount_info - mount_info
            description = ("mounted partitions are different after reboot "
                           "(old entries: %s, new entries: %s)" %
                           (old_entries, new_entries))
            self._record_reboot_failure(subdir, "reboot.verify_config",
                                        description, running_id=running_id)
            raise error.JobError("Reboot failed: %s" % description)


    def end_reboot(self, subdir, kernel, patches, running_id=None):
        self._check_post_reboot(subdir, running_id=running_id)

        # strip ::<timestamp> from the kernel version if present
        kernel = kernel.split("::")[0]
        kernel_info = {"kernel": kernel}
        for i, patch in enumerate(patches):
            kernel_info["patch%d" % i] = patch
        self._decrement_group_level()
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

            @param device: e.g. /dev/sda2, /dev/sdb1 etc...
            @param mountpoint: Specify a directory to mount to. If not specified
                               autotest tmp directory will be used.
            @param loop_size: Size of loopback device (in MB). Defaults to 0.

            @return: A L{client.bin.partition.partition} object
        """

        if not mountpoint:
            mountpoint = self.tmpdir
        return partition_lib.partition(self, device, loop_size, mountpoint)

    @utils.deprecated
    def filesystem(self, device, mountpoint=None, loop_size=0):
        """ Same as partition

        @deprecated: Use partition method instead
        """
        return self.partition(device, loop_size, mountpoint)


    def enable_external_logging(self):
        pass


    def disable_external_logging(self):
        pass


    def enable_test_cleanup(self):
        """ By default tests run test.cleanup """
        self.set_state("__run_test_cleanup", True)
        self.run_test_cleanup = True


    def disable_test_cleanup(self):
        """ By default tests do not run test.cleanup """
        self.set_state("__run_test_cleanup", False)
        self.run_test_cleanup = False


    def default_test_cleanup(self, val):
        if not self._is_continuation:
            self.set_state("__run_test_cleanup", val)
            self.run_test_cleanup = val


    def default_boot_tag(self, tag):
        if not self._is_continuation:
            self.set_state("__last_boot_tag", tag)
            self.last_boot_tag = tag


    def default_tag(self, tag):
        """Allows the scheduler's job tag to be passed in from autoserv."""
        if not self._is_continuation:
            self.set_state("__job_tag", tag)
            self.tag = tag


    def reboot_setup(self):
        # save the partition list and their mount point and compare it
        # after reboot
        partition_list = partition_lib.get_partition_list(self)
        mount_info = set((p.device, p.get_mountpoint()) for p in partition_list)
        self.set_state("__mount_info", mount_info)


    def reboot(self, tag=LAST_BOOT_TAG):
        if tag == LAST_BOOT_TAG:
            tag = self.last_boot_tag
        else:
            self.set_state("__last_boot_tag", tag)
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

        utils.system("(sleep 5; reboot) </dev/null >/dev/null 2>&1 &")
        self.quit()


    def noop(self, text):
        logging.info("job: noop: " + text)


    @_run_test_complete_on_exit
    def parallel(self, *tasklist):
        """Run tasks in parallel"""

        pids = []
        old_log_filename = self.log_filename
        for i, task in enumerate(tasklist):
            assert isinstance(task, (tuple, list))
            self.log_filename = old_log_filename + (".%d" % i)
            task_func = lambda: task[0](*task[1:])
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

        self.log_filename = old_log_filename

        # handle any exceptions raised by the parallel tasks
        if exceptions:
            msg = "%d task(s) failed in job.parallel" % len(exceptions)
            raise error.JobError(msg)


    def quit(self):
        # XXX: should have a better name.
        self.harness.run_pause()
        raise error.JobContinue("more to come")


    def complete(self, status):
        """Clean up and exit"""
        # We are about to exit 'complete' so clean up the control file.
        dest = os.path.join(self.resultdir, os.path.basename(self.state_file))
        os.rename(self.state_file, dest)

        self.harness.run_complete()
        self.disable_external_logging()
        sys.exit(status)


    def set_state(self, var, val):
        # Deep copies make sure that the state can't be altered
        # without it being re-written.  Perf wise, deep copies
        # are overshadowed by pickling/loading.
        self.state[var] = copy.deepcopy(val)
        outfile = open(self.state_file, 'wb')
        try:
            pickle.dump(self.state, outfile, pickle.HIGHEST_PROTOCOL)
        finally:
            outfile.close()
        logging.debug("Persistent state variable %s now set to %r", var, val)


    def _load_state(self):
        if hasattr(self, 'state'):
            raise RuntimeError('state already exists')
        infile = None
        try:
            try:
                infile = open(self.state_file, 'rb')
                self.state = pickle.load(infile)
                logging.info('Loaded state from %s', self.state_file)
            except IOError:
                self.state = {}
                initialize = True
        finally:
            if infile:
                infile.close()

        initialize = '__steps' not in self.state
        if not (self._is_continuation or initialize):
            raise RuntimeError('Loaded state must contain __steps or be a '
                               'continuation.')

        if initialize:
            logging.info('Initializing the state engine')
            self.set_state('__steps', [])  # writes pickle file


    def get_state(self, var, default=NO_DEFAULT):
        if var in self.state or default == NO_DEFAULT:
            val = self.state[var]
        else:
            val = default
        return copy.deepcopy(val)


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
        ancestry = copy.copy(self.current_step_ancestry)
        return (ancestry, fn, args, dargs)


    def next_step_append(self, fn, *args, **dargs):
        """Define the next step and place it at the end"""
        steps = self.get_state('__steps')
        steps.append(self.__create_step_tuple(fn, args, dargs))
        self.set_state('__steps', steps)


    def next_step(self, fn, *args, **dargs):
        """Create a new step and place it after any steps added
        while running the current step but before any steps added in
        previous steps"""
        steps = self.get_state('__steps')
        steps.insert(self.next_step_index,
                     self.__create_step_tuple(fn, args, dargs))
        self.next_step_index += 1
        self.set_state('__steps', steps)


    def next_step_prepend(self, fn, *args, **dargs):
        """Insert a new step, executing first"""
        steps = self.get_state('__steps')
        steps.insert(0, self.__create_step_tuple(fn, args, dargs))
        self.next_step_index += 1
        self.set_state('__steps', steps)


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
            self.current_step_ancestry.append(current_function)
            self.next_step_prepend('step_init')


    def step_engine(self):
        """The multi-run engine used when the control file defines step_init.

        Does the next step.
        """

        # Set up the environment and then interpret the control file.
        # Some control files will have code outside of functions,
        # which means we need to have our state engine initialized
        # before reading in the file.
        global_control_vars = {'job': self}
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

        # Iterate through the steps.  If we reboot, we'll simply
        # continue iterating on the next step.
        while len(self.get_state('__steps')) > 0:
            steps = self.get_state('__steps')
            (ancestry, fn_name, args, dargs) = steps.pop(0)
            self.set_state('__steps', steps)

            self.next_step_index = 0
            ret = self._create_frame(global_control_vars, ancestry, fn_name)
            local_vars, self.current_step_ancestry = ret
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
        state = self.get_state("__sysinfo", None)
        if state:
            self.sysinfo.deserialize(state)


    def _save_sysinfo_state(self):
        state = self.sysinfo.serialize()
        self.set_state("__sysinfo", state)


    def _init_group_level(self):
        self.group_level = self.get_state("__group_level", default=0)


    def _increment_group_level(self):
        self.group_level += 1
        self.set_state("__group_level", self.group_level)


    def _decrement_group_level(self):
        self.group_level -= 1
        self.set_state("__group_level", self.group_level)


    def record(self, status_code, subdir, operation, status = '',
               optional_fields=None):
        """
        Record job-level status

        The intent is to make this file both machine parseable and
        human readable. That involves a little more complexity, but
        really isn't all that bad ;-)

        Format is <status code>\t<subdir>\t<operation>\t<status>

        status code: (GOOD|WARN|FAIL|ABORT)
                or   START
                or   END (GOOD|WARN|FAIL|ABORT)

        subdir: MUST be a relevant subdirectory in the results,
        or None, which will be represented as '----'

        operation: description of what you ran (e.g. "dbench", or
                                        "mkfs -t foobar /dev/sda9")

        status: error message or "completed sucessfully"

        ------------------------------------------------------------

        Initial tabs indicate indent levels for grouping, and is
        governed by self.group_level

        multiline messages have secondary lines prefaced by a double
        space ('  ')
        """

        if subdir:
            if re.match(r'[\n\t]', subdir):
                raise ValueError("Invalid character in subdir string")
            substr = subdir
        else:
            substr = '----'

        if not log.is_valid_status(status_code):
            raise ValueError("Invalid status code supplied: %s" % status_code)
        if not operation:
            operation = '----'

        if re.match(r'[\n\t]', operation):
            raise ValueError("Invalid character in operation string")
        operation = operation.rstrip()

        if not optional_fields:
            optional_fields = {}

        status = status.rstrip()
        status = re.sub(r"\t", "  ", status)
        # Ensure any continuation lines are marked so we can
        # detect them in the status file to ensure it is parsable.
        status = re.sub(r"\n", "\n" + "\t" * self.group_level + "  ", status)

        # Generate timestamps for inclusion in the logs
        epoch_time = int(time.time())  # seconds since epoch, in UTC
        local_time = time.localtime(epoch_time)
        optional_fields["timestamp"] = str(epoch_time)
        optional_fields["localtime"] = time.strftime("%b %d %H:%M:%S",
                                                     local_time)

        fields = [status_code, substr, operation]
        fields += ["%s=%s" % x for x in optional_fields.iteritems()]
        fields.append(status)

        msg = '\t'.join(str(x) for x in fields)
        msg = '\t' * self.group_level + msg

        msg_tag = ""
        if "." in self.log_filename:
            msg_tag = self.log_filename.split(".", 1)[1]

        self.harness.test_status_detail(status_code, substr, operation, status,
                                        msg_tag)
        self.harness.test_status(msg, msg_tag)

        # log to stdout (if enabled)
        #if self.log_filename == self.DEFAULT_LOG_FILENAME:
        logging.info(msg)

        # log to the "root" status log
        status_file = os.path.join(self.resultdir, self.log_filename)
        open(status_file, "a").write(msg + "\n")

        # log to the subdir status log (if subdir is set)
        if subdir:
            dir = os.path.join(self.resultdir, subdir)
            status_file = os.path.join(dir, self.DEFAULT_LOG_FILENAME)
            open(status_file, "a").write(msg + "\n")


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
        mb_per_sec = bytes_per_sec / 1024**2
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


def runjob(control, options):
    """
    Run a job using the given control file.

    This is the main interface to this module.

    @see base_job.__init__ for parameter info.
    """
    control = os.path.abspath(control)
    state = control + '.state'
    # Ensure state file is cleaned up before the job starts to run if autotest
    # is not running with the --continue flag
    if not options.cont and os.path.isfile(state):
        logging.debug('Cleaning up previously found state file')
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

        myjob = job(control, options)

        # Load in the users control file, may do any one of:
        #  1) execute in toto
        #  2) define steps, and select the first via next_step()
        myjob.step_engine()

    except error.JobContinue:
        sys.exit(5)

    except error.JobComplete:
        sys.exit(1)

    except error.JobError, instance:
        logging.error("JOB ERROR: " + instance.args[0])
        if myjob:
            command = None
            if len(instance.args) > 1:
                command = instance.args[1]
                myjob.record('ABORT', None, command, instance.args[0])
            myjob._decrement_group_level()
            myjob.record('END ABORT', None, None, instance.args[0])
            assert (myjob.group_level == 0), ('myjob.group_level must be 0,'
                                              ' not %d' % myjob.group_level)
            myjob.complete(1)
        else:
            sys.exit(1)

    except Exception, e:
        # NOTE: job._run_step_fn and job.step_engine will turn things into
        # a JobError for us.  If we get here, its likely an autotest bug.
        msg = str(e) + '\n' + traceback.format_exc()
        logging.critical("JOB ERROR (autotest bug?): " + msg)
        if myjob:
            myjob._decrement_group_level()
            myjob.record('END ABORT', None, None, msg)
            assert(myjob.group_level == 0)
            myjob.complete(1)
        else:
            sys.exit(1)

    # If we get here, then we assume the job is complete and good.
    myjob._decrement_group_level()
    myjob.record('END GOOD', None, None)
    assert(myjob.group_level == 0)

    myjob.complete(0)


site_job = utils.import_site_class(
    __file__, "autotest_lib.client.bin.site_job", "site_job", base_job)

class job(site_job):
    pass
