"""The main job wrapper

This is the core infrastructure.
"""

__author__ = """Copyright Andy Whitcroft, Martin J. Bligh 2006"""

# standard stuff
import os, sys, re, pickle, shutil, time, traceback, types, copy

# autotest stuff
from autotest_lib.client.bin import autotest_utils, parallel, kernel, xen
from autotest_lib.client.bin import profilers, fd_stack, boottool, harness
from autotest_lib.client.bin import config, sysinfo, cpuset, test, filesystem
from autotest_lib.client.common_lib import error, barrier, log, utils
from autotest_lib.client.common_lib import packages, debug

JOB_PREAMBLE = """
from autotest_lib.client.common_lib.error import *
from autotest_lib.client.common_lib.utils import *
from autotest_lib.client.bin.autotest_utils import *
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
            stdout
                    fd_stack object for stdout
            stderr
                    fd_stack object for stderr
            profilers
                    the profilers object for this job
            harness
                    the server harness object for this job
            config
                    the job configuration for this job
    """

    DEFAULT_LOG_FILENAME = "status"

    def __init__(self, control, jobtag, cont, harness_type=None,
                    use_external_logging = False):
        """
                control
                        The control file (pathname of)
                jobtag
                        The job tag string (eg "default")
                cont
                        If this is the continuation of this job
                harness_type
                        An alternative server harness
        """
        self.drop_caches = True
        self.autodir = os.environ['AUTODIR']
        self.bindir = os.path.join(self.autodir, 'bin')
        self.libdir = os.path.join(self.autodir, 'lib')
        self.testdir = os.path.join(self.autodir, 'tests')
        self.site_testdir = os.path.join(self.autodir, 'site_tests')
        self.profdir = os.path.join(self.autodir, 'profilers')
        self.tmpdir = os.path.join(self.autodir, 'tmp')
        self.toolsdir = os.path.join(self.autodir, 'tools')
        self.resultdir = os.path.join(self.autodir, 'results', jobtag)
        self.sysinfo = sysinfo.sysinfo(self.resultdir)
        self.control = os.path.abspath(control)
        self.state_file = self.control + '.state'
        self.current_step_ancestry = []
        self.next_step_index = 0
        self.testtag = ''
        self._load_state()
        self.pkgmgr = packages.PackageManager(
            self.autodir, run_function_dargs={'timeout':600})
        self.pkgdir = os.path.join(self.autodir, 'packages')
        self.run_test_cleanup = self.get_state("__run_test_cleanup",
                                                default=True)
        self.job_log = debug.get_logger(module='client')

        if not cont:
            """
            Don't cleanup the tmp dir (which contains the lockfile)
            in the constructor, this would be a problem for multiple
            jobs starting at the same time on the same client. Instead
            do the delete at the server side. We simply create the tmp
            directory here if it does not already exist.
            """
            if not os.path.exists(self.tmpdir):
                os.mkdir(self.tmpdir)

            if not os.path.exists(self.pkgdir):
                os.mkdir(self.pkgdir)

            results = os.path.join(self.autodir, 'results')
            if not os.path.exists(results):
                os.mkdir(results)

            download = os.path.join(self.testdir, 'download')
            if not os.path.exists(download):
                os.mkdir(download)

            if os.path.exists(self.resultdir):
                utils.system('rm -rf ' + self.resultdir)
            os.mkdir(self.resultdir)

            os.mkdir(os.path.join(self.resultdir, 'debug'))
            os.mkdir(os.path.join(self.resultdir, 'analysis'))

            shutil.copyfile(self.control,
                            os.path.join(self.resultdir, 'control'))


        self.control = control
        self.jobtag = jobtag
        self.log_filename = self.DEFAULT_LOG_FILENAME
        self.container = None

        self.stdout = fd_stack.fd_stack(1, sys.stdout)
        self.stderr = fd_stack.fd_stack(2, sys.stderr)

        self._init_group_level()

        self.config = config.config(self)
        self.harness = harness.select(harness_type, self)
        self.profilers = profilers.profilers(self)

        try:
            tool = self.config_get('boottool.executable')
            self.bootloader = boottool.boottool(tool)
        except:
            pass

        self.sysinfo.log_per_reboot_data()

        if not cont:
            self.record('START', None, None)
            self._increment_group_level()

        self.harness.run_start()

        if use_external_logging:
            self.enable_external_logging()

        # load the max disk usage rate - default to no monitoring
        self.max_disk_usage_rate = self.get_state('__monitor_disk', default=0.0)


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
        if len(self.pkgmgr.repo_urls) > 0:
            self.pkgmgr.install_pkg(name, pkg_type,
                                    self.pkgdir, install_dir)


    def add_repository(self, repo_urls):
        '''
        Adds the repository locations to the job so that packages
        can be fetched from them when needed. The repository list
        needs to be a string list
        Ex: job.add_repository(['http://blah1','http://blah2'])
        '''
        # TODO(aganti): Validate the list of the repository URLs.
        repositories = repo_urls + self.pkgmgr.repo_urls
        self.pkgmgr = packages.PackageManager(
            self.autodir, repo_urls=repositories,
            run_function_dargs={'timeout':600})
        # Fetch the packages' checksum file that contains the checksums
        # of all the packages if it is not already fetched. The checksum
        # is always fetched whenever a job is first started. This
        # is not done in the job's constructor as we don't have the list of
        # the repositories there (and obviously don't care about this file
        # if we are not using the repos)
        try:
            checksum_file_path = os.path.join(self.pkgmgr.pkgmgr_dir,
                                              packages.CHECKSUM_FILE)
            self.pkgmgr.fetch_pkg(packages.CHECKSUM_FILE, checksum_file_path,
                                  use_checksum=False)
        except packages.PackageFetchError, e:
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
            except packages.PackageInstallError:
                # see if the dep is there locally
                pass

            # dep_dir might not exist if it is not fetched from the repos
            if not os.path.exists(dep_dir):
                raise error.TestError("Dependency %s does not exist" % dep)

            os.chdir(dep_dir)
            utils.system('./' + dep + '.py')


    def _runtest(self, url, tag, args, dargs):
        try:
            try:
                l = lambda : test.runtest(self, url, tag, args, dargs)
                pid = parallel.fork_start(self.resultdir, l)
                parallel.fork_waitfor(self.resultdir, pid)
            except error.TestBaseException:
                raise
            except Exception, e:
                raise error.UnhandledTestError(e)
        finally:
            # Reset the logging level to client level
            debug.configure(module='client')


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
        os.mkdir(outputdir)

        container = dargs.pop('container', None)
        if container:
            cname = container.get('name', None)
            if not cname:   # get old name
                cname = container.get('container_name', None)
            mbytes = container.get('mbytes', None)
            if not mbytes:  # get old name
                mbytes = container.get('mem', None)
            cpus  = container.get('cpus', None)
            if not cpus:    # get old name
                cpus  = container.get('cpu', None)
            root  = container.get('root', None)
            network = container.get('network', None)
            disk = container.get('disk', None)
            try:
                self.new_container(mbytes=mbytes, cpus=cpus, root=root,
                                   name=cname, network=network, disk=disk)
            except cpuset.CpusetsNotAvailable, e:
                self.record("START", subdir, testname)
                self._increment_group_level()
                self.record("ERROR", subdir, testname, str(e))
                self._decrement_group_level()
                self.record("END ERROR", subdir, testname)
                return False
            # We are running in a container now...

        def log_warning(reason):
            self.record("WARN", subdir, testname, reason)
        @disk_usage_monitor.watch(log_warning, "/", self.max_disk_usage_rate)
        def group_func():
            try:
                self._runtest(url, tag, args, dargs)
            except error.TestBaseException, detail:
                self.record(detail.exit_status, subdir, testname,
                            str(detail))
                raise
            except Exception, detail:
                self.record('FAIL', subdir, testname,
                            str(detail))
                raise
            else:
                self.record('GOOD', subdir, testname,
                            'completed successfully')

        result, exc_info = self._rungroup(subdir, testname, group_func)
        if container:
            self.release_container()
        if exc_info and isinstance(exc_info[1], error.TestBaseException):
            return False
        elif exc_info:
            raise exc_info[0], exc_info[1], exc_info[2]
        else:
            return True


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

        Returns a 2-tuple (result, exc_info) where result
        is the return value of function, and exc_info is
        the sys.exc_info() of the exception thrown by the
        function (which may be None).
        """

        result, exc_info = None, None
        try:
            self.record('START', subdir, testname)
            self._increment_group_level()
            result = function(*args, **dargs)
            self._decrement_group_level()
            self.record('END GOOD', subdir, testname)
        except error.TestBaseException, e:
            exc_info = sys.exc_info()
            self._decrement_group_level()
            self.record('END %s' % e.exit_status, subdir, testname, str(e))
        except Exception, e:
            exc_info = sys.exc_info()
            self._decrement_group_level()
            err_msg = str(e) + '\n' + traceback.format_exc()
            self.record('END FAIL', subdir, testname, err_msg)

        return result, exc_info


    def run_group(self, function, *args, **dargs):
        """\
        function:
                subroutine to run
        *args:
                arguments for the function
        """

        # Allow the tag for the group to be specified
        name = function.__name__
        tag = dargs.pop('tag', None)
        if tag:
            name = tag

        outputdir = os.path.join(self.resultdir, name)
        if os.path.exists(outputdir):
            msg = ("%s already exists, test <%s> may have"
                    " already run with tag <%s>"
                    % (outputdir, name, name) )
            raise error.TestError(msg)
        os.mkdir(outputdir)

        result, exc_info = self._rungroup(name, name, function, *args, **dargs)

        # if there was a non-TestError exception, raise it
        if exc_info and not isinstance(exc_info[1], error.TestError):
            err = ''.join(traceback.format_exception(*exc_info))
            raise error.TestError(name + ' failed\n' + err)

        # pass back the actual return value from the function
        return result


    def set_test_tag(self, tag=''):
        # set tag to be added to test name of all following run_test() steps
        self.testtag = tag


    def new_container(self, mbytes=None, cpus=None, root=None, name=None,
                      network=None, disk=None, kswapd_merge=False):
        if not autotest_utils.grep('cpuset', '/proc/filesystems'):
            print "Containers not enabled by latest reboot"
            return  # containers weren't enabled in this kernel boot
        pid = os.getpid()
        if not name:
            name = 'test%d' % pid  # make arbitrary unique name
        self.container = cpuset.cpuset(name, job_size=mbytes, job_pid=pid, 
                                       cpus=cpus, root=root, network=network, 
                                       disk=disk, kswapd_merge=kswapd_merge)
        # This job's python shell is now running in the new container
        # and all forked test processes will inherit that container


    def release_container(self):
        if self.container:
            self.container = self.container.release()


    def cpu_count(self):
        if self.container:
            return len(self.container.cpus)
        return autotest_utils.count_cpus()  # use total system count


    def end_reboot(self, subdir, kernel, patches):
        kernel_info = {"kernel": kernel}
        for i, patch in enumerate(patches):
            kernel_info["patch%d" % i] = patch
        self._decrement_group_level()
        self.record("END GOOD", subdir, "reboot", optional_fields=kernel_info)


    def end_reboot_and_verify(self, expected_when, expected_id, subdir,
                              type='src', patches=[]):
        """ Check the passed kernel identifier against the command line
            and the running kernel, abort the job on missmatch. """

        print (("POST BOOT: checking booted kernel " +
                "mark=%d identity='%s' type='%s'") %
               (expected_when, expected_id, type))

        running_id = autotest_utils.running_os_ident()

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
            print "check_kernel_ident: kernel identifier mismatch"
            bad = True
        if expected_when != cmdline_when:
            print "check_kernel_ident: kernel command line mismatch"
            bad = True

        if bad:
            print "   Expected Ident: " + expected_id
            print "    Running Ident: " + running_id
            print "    Expected Mark: %d" % (expected_when)
            print "Command Line Mark: %d" % (cmdline_when)
            print "     Command Line: " + cmdline

            self.record("ABORT", subdir, "reboot.verify", "boot failure")
            self._decrement_group_level()
            kernel = {"kernel": running_id.split("::")[0]}
            self.record("END ABORT", subdir, 'reboot', optional_fields=kernel)
            raise error.JobError("reboot returned with the wrong kernel")

        self.record('GOOD', subdir, 'reboot.verify', expected_id)
        self.end_reboot(subdir, expected_id, patches)


    def filesystem(self, device, mountpoint = None, loop_size = 0):
        if not mountpoint:
            mountpoint = self.tmpdir
        return filesystem.filesystem(self, device, mountpoint,loop_size)


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


    def reboot_setup(self):
        pass


    def reboot(self, tag='autotest'):
        self.reboot_setup()
        self.record('START', None, 'reboot')
        self._increment_group_level()
        self.record('GOOD', None, 'reboot.start')
        self.harness.run_reboot()
        default = self.config_get('boot.set_default')
        if default:
            self.bootloader.set_default(tag)
        else:
            self.bootloader.boot_once(tag)

        # HACK: using this as a module sometimes hangs shutdown, so if it's
        # installed unload it first
        utils.system("modprobe -r netconsole", ignore_status=True)

        cmd = "(sleep 5; reboot) </dev/null >/dev/null 2>&1 &"
        utils.system(cmd)
        self.quit()


    def noop(self, text):
        print "job: noop: " + text


    @_run_test_complete_on_exit
    def parallel(self, *tasklist):
        """Run tasks in parallel"""

        pids = []
        old_log_filename = self.log_filename
        for i, task in enumerate(tasklist):
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
        pickle.dump(self.state, open(self.state_file, 'w'))
        print "Persistant state variable %s now set to %r" % (var, val)


    def _load_state(self):
        assert not hasattr(self, "state")
        try:
            self.state = pickle.load(open(self.state_file, 'r'))
            self.state_existed = True
        except Exception:
            print "Initializing the state engine."
            self.state = {}
            self.set_state('__steps', []) # writes pickle file
            self.state_existed = False


    def get_state(self, var, default=None):
        if var in self.state or default == None:
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
        # Pickling actual functions is harry, thus we have to call
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
        exec('__ret = %s(*__args, **__dargs)' % fn, local_vars, local_vars)
        return local_vars['__ret']


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
        """the stepping engine -- if the control file defines
        step_init we will be using this engine to drive multiple runs.
        """
        """Do the next step"""

        # Set up the environment and then interpret the control file.
        # Some control files will have code outside of functions,
        # which means we need to have our state engine initialized
        # before reading in the file.
        global_control_vars = {'job': self}
        exec(JOB_PREAMBLE, global_control_vars, global_control_vars)
        execfile(self.control, global_control_vars, global_control_vars)

        # If we loaded in a mid-job state file, then we presumably
        # know what steps we have yet to run.
        if not self.state_existed:
            if global_control_vars.has_key('step_init'):
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
        status = re.sub(r"\r", "", status)
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
        print msg

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
        self.initial_space = autotest_utils.freespace(self.device)
        self.start_time = time.time()


    def stop(self):
        # if no maximum usage rate was set, we don't need to
        # generate any warnings
        if not self.max_mb_per_hour:
            return

        final_space = autotest_utils.freespace(self.device)
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


def runjob(control, cont = False, tag = "default", harness_type = '',
           use_external_logging = False):
    """The main interface to this module

    control
            The control file to use for this job.
    cont
            Whether this is the continuation of a previously started job
    """
    control = os.path.abspath(control)
    state = control + '.state'

    # instantiate the job object ready for the control file.
    myjob = None
    try:
        # Check that the control file is valid
        if not os.path.exists(control):
            raise error.JobError(control + ": control file not found")

        # When continuing, the job is complete when there is no
        # state file, ensure we don't try and continue.
        if cont and not os.path.exists(state):
            raise error.JobComplete("all done")
        if cont == False and os.path.exists(state):
            os.unlink(state)

        myjob = job(control, tag, cont, harness_type, use_external_logging)

        # Load in the users control file, may do any one of:
        #  1) execute in toto
        #  2) define steps, and select the first via next_step()
        myjob.step_engine()

    except error.JobContinue:
        sys.exit(5)

    except error.JobComplete:
        sys.exit(1)

    except error.JobError, instance:
        print "JOB ERROR: " + instance.args[0]
        if myjob:
            command = None
            if len(instance.args) > 1:
                command = instance.args[1]
                myjob.record('ABORT', None, command, instance.args[0])
            myjob._decrement_group_level()
            myjob.record('END ABORT', None, None, instance.args[0])
            assert(myjob.group_level == 0)
            myjob.complete(1)
        else:
            sys.exit(1)

    except Exception, e:
        msg = str(e) + '\n' + traceback.format_exc()
        print "JOB ERROR: " + msg
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


# site_job.py may be non-existant or empty, make sure that an appropriate
# site_job class is created nevertheless
try:
    from autotest_lib.client.bin.site_job import site_job
except ImportError:
    class site_job(object):
        pass

class job(site_job, base_job):
    pass
