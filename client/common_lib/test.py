# Shell class for a test, inherited by all individual tests
#
# Methods:
#       __init__        initialise
#       initialize      run once for each job
#       setup           run once for each new version of the test installed
#       run             run the test (wrapped by job.run_test())
#
# Data:
#       job             backreference to the job this test instance is part of
#       outputdir       eg. results/<job>/<testname.tag>
#       resultsdir      eg. results/<job>/<testname.tag>/results
#       profdir         eg. results/<job>/<testname.tag>/profiling
#       debugdir        eg. results/<job>/<testname.tag>/debug
#       bindir          eg. tests/<test>
#       src             eg. tests/<test>/src
#       tmpdir          eg. tmp/<tempname>_<testname.tag>

import fcntl, os, re, sys, shutil, tarfile, tempfile, time, traceback
import warnings, logging

from autotest_lib.client.common_lib import error, packages
from autotest_lib.client.bin import utils


class base_test:
    preserve_srcdir = False

    def __init__(self, job, bindir, outputdir):
        self.job = job
        self.pkgmgr = job.pkgmgr
        self.autodir = job.autodir

        self.outputdir = outputdir
        self.tagged_testname = os.path.basename(self.outputdir)
        self.resultsdir = os.path.join(self.outputdir, 'results')
        os.mkdir(self.resultsdir)
        self.profdir = os.path.join(self.outputdir, 'profiling')
        os.mkdir(self.profdir)
        self.debugdir = os.path.join(self.outputdir, 'debug')
        os.mkdir(self.debugdir)
        self.bindir = bindir
        if hasattr(job, 'libdir'):
            self.libdir = job.libdir
        self.srcdir = os.path.join(self.bindir, 'src')
        self.tmpdir = tempfile.mkdtemp("_" + self.tagged_testname, 
                                       dir=job.tmpdir)


    def assert_(self, expr, msg='Assertion failed.'):
        if not expr:
            raise error.TestError(msg)


    def write_test_keyval(self, attr_dict):
        utils.write_keyval(self.outputdir, attr_dict)


    @staticmethod
    def _append_type_to_keys(dictionary, typename):
        new_dict = {}
        for key, value in dictionary.iteritems():
            new_key = "%s{%s}" % (key, typename)
            new_dict[new_key] = value
        return new_dict


    def write_perf_keyval(self, perf_dict):
        self.write_iteration_keyval({}, perf_dict)


    def write_attr_keyval(self, attr_dict):
        self.write_iteration_keyval(attr_dict, {})


    def write_iteration_keyval(self, attr_dict, perf_dict):
        if attr_dict:
            attr_dict = self._append_type_to_keys(attr_dict, "attr")
            utils.write_keyval(self.resultsdir, attr_dict, type_tag="attr")

        if perf_dict:
            perf_dict = self._append_type_to_keys(perf_dict, "perf")
            utils.write_keyval(self.resultsdir, perf_dict, type_tag="perf")

        keyval_path = os.path.join(self.resultsdir, "keyval")
        print >> open(keyval_path, "a"), ""


    def initialize(self):
        pass


    def setup(self):
        pass


    def warmup(self, *args, **dargs):
        pass


    def drop_caches_between_iterations(self):
        if self.job.drop_caches_between_iterations:
            print "Dropping caches between iterations"
            utils.drop_caches()


    def _call_run_once(self, args, dargs):
        self.drop_caches_between_iterations()
        self.run_once(*args, **dargs)
        self.postprocess_iteration()


    def execute(self, iterations=None, test_length=None, profile_only=False,
                _get_time=time.time, postprocess_profiled_run=None,
                *args, **dargs):
        """
        This is the basic execute method for the tests inherited from base_test.
        If you want to implement a benchmark test, it's better to implement
        the run_once function, to cope with the profiling infrastructure. For
        other tests, you can just override the default implementation.

        @param test_length: The minimum test length in seconds. We'll run the
            run_once function for a number of times large enough to cover the
            minimum test length.

        @param iterations: A number of iterations that we'll run the run_once
            function. This parameter is incompatible with test_length and will
            be silently ignored if you specify both.

        @param profile_only: Do not run any test iterations before running
            the test under the profiler.  This is equivalent to specifying
            iterations=0 but is much easier to remember/read/comprehend when
            making control files with job.run_test(profile_only=True) in it
            rather than job.run_test(iterations=0).

        @param _get_time: [time.time] Used for unit test time injection.

        @param postprocess_profiled_run: Run the postprocessing for the
            profiled run.
        """

        self.warmup(*args, **dargs)
        # For our special class of tests, the benchmarks, we don't want
        # profilers to run during the test iterations. Let's reserve only
        # the last iteration for profiling, if needed. So let's stop
        # all profilers if they are present and active.
        profilers = self.job.profilers
        if profilers.active():
            profilers.stop(self)
        # If the user called this test in an odd way (specified both iterations
        # and test_length), let's warn them.
        if iterations and test_length:
            logging.info(
                    'Iterations parameter ignored (timed execution).')
        if test_length:
            test_start = _get_time()
            time_elapsed = 0
            timed_counter = 0
            logging.info('Test started. Minimum test length: %d s',
                               test_length)
            while time_elapsed < test_length:
                timed_counter = timed_counter + 1
                if time_elapsed == 0:
                    logging.info('Executing iteration %d', timed_counter)
                elif time_elapsed > 0:
                    logging.info(
                            'Executing iteration %d, time_elapsed %d s',
                            timed_counter, time_elapsed)
                self._call_run_once(args, dargs)
                test_iteration_finish = _get_time()
                time_elapsed = test_iteration_finish - test_start
            logging.info('Test finished after %d iterations',
                               timed_counter)
            logging.info('Time elapsed: %d s', time_elapsed)
        else:
            orig_iterations = iterations
            if profile_only:
                if iterations:
                    logging.info('Iterations parameter ignored '
                                       '(profile_only=True).')
                iterations = 0
            elif iterations is None:
                iterations = 1
            if iterations:
                logging.info('Test started. '
                                   'Number of iterations: %d', iterations)
                for self.iteration in xrange(1, iterations+1):
                    logging.info('Executing iteration %d of %d',
                                       self.iteration, iterations)
                    self._call_run_once(args, dargs)
                logging.info('Test finished after %d iterations.',
                                   iterations)

        self.run_once_profiling(postprocess_profiled_run, *args, **dargs)

        # Do any postprocessing, normally extracting performance keyvals, etc
        self.postprocess()


    def run_once_profiling(self, postprocess_profiled_run, *args, **dargs):
        profilers = self.job.profilers
        # Do a profiling run if necessary
        if profilers.present():
            self.drop_caches_between_iterations()
            profilers.start(self)
            print 'Profilers present. Profiling run started'
            try:
                self.iteration = 0       # indicator this is a profiling run
                self.run_once(*args, **dargs)

                # Priority to the run_once() argument over the attribute.
                postprocess_attribute = getattr(self,
                                                'postprocess_profiled_run',
                                                False)

                if (postprocess_profiled_run or
                    (postprocess_profiled_run is None and
                     postprocess_attribute)):
                    self.postprocess_iteration()

            finally:
                profilers.stop(self)
                profilers.report(self)


    def postprocess(self):
        pass


    def postprocess_iteration(self):
        pass


    def cleanup(self):
        pass


    def _run_cleanup(self, args, dargs):
        """Call self.cleanup and convert exceptions as appropriate.

        Args:
          args: An argument tuple to pass to cleanup.
          dargs: A dictionary of with potential keyword arguments for cleanup.
        """
        p_args, p_dargs = _cherry_pick_args(self.cleanup, args, dargs)
        try:
            self.cleanup(*p_args, **p_dargs)
        except error.AutotestError:
            raise
        except Exception, e:
            # Other exceptions must be treated as a ERROR when
            # raised during the cleanup() phase.
            raise error.UnhandledTestError(e)


    def _setup_test_logging_handler(self):
        """
        Adds a file handler during test execution, which will give test writers
        the ability to obtain test results on the test results dir just by 
        making logging calls.
        """
        result_filename = os.path.join(self.resultsdir, 
                                       '%s.log' % self.tagged_testname)
        self.test_handler = logging.FileHandler(filename=result_filename,
                                                mode='w')
        fmt_str = '[%(asctime)s - %(module)-15s - %(levelname)-8s] %(message)s'
        self.test_formatter = logging.Formatter(fmt_str)
        self.test_handler.setFormatter(self.test_formatter)
        self.logger = logging.getLogger()
        self.logger.addHandler(self.test_handler)


    def _exec(self, args, dargs):

        self.job.stdout.tee_redirect(os.path.join(self.debugdir, 'stdout'))
        self.job.stderr.tee_redirect(os.path.join(self.debugdir, 'stderr'))
        self._setup_test_logging_handler()
        try:
            # write out the test attributes into a keyval
            dargs   = dargs.copy()
            run_cleanup = dargs.pop('run_cleanup', self.job.run_test_cleanup)
            keyvals = dargs.pop('test_attributes', {}).copy()
            keyvals['version'] = self.version
            for i, arg in enumerate(args):
                keyvals['param-%d' % i] = repr(arg)
            for name, arg in dargs.iteritems():
                keyvals['param-%s' % name] = repr(arg)
            self.write_test_keyval(keyvals)

            _validate_args(args, dargs, self.initialize, self.setup,
                           self.execute, self.cleanup)

            try:
                # Initialize:
                p_args, p_dargs = _cherry_pick_args(self.initialize,args,dargs)
                self.initialize(*p_args, **p_dargs)

                lockfile = open(os.path.join(self.job.tmpdir, '.testlock'), 'w')
                try:
                    fcntl.flock(lockfile, fcntl.LOCK_EX)
                    # Setup: (compile and install the test, if needed)
                    p_args, p_dargs = _cherry_pick_args(self.setup,args,dargs)
                    utils.update_version(self.srcdir, self.preserve_srcdir,
                                         self.version, self.setup,
                                         *p_args, **p_dargs)
                finally:
                    fcntl.flock(lockfile, fcntl.LOCK_UN)
                    lockfile.close()

                # Execute:
                os.chdir(self.outputdir)
                if hasattr(self, 'run_once'):
                    p_args, p_dargs = _cherry_pick_args(self.run_once,
                                                        args, dargs)
                    # pull in any non-* and non-** args from self.execute
                    for param in _get_nonstar_args(self.execute):
                        if param in dargs:
                            p_dargs[param] = dargs[param]
                else:
                    p_args, p_dargs = _cherry_pick_args(self.execute,
                                                        args, dargs)
                try:
                    self.execute(*p_args, **p_dargs)
                except error.AutotestError:
                    # Pass already-categorized errors on up as is.
                    raise
                except Exception, e:
                    # Other exceptions must be treated as a FAIL when
                    # raised during the execute() phase.
                    raise error.UnhandledTestFail(e)
            except Exception:
                # Save the exception while we run our cleanup() before
                # reraising it.
                exc_info = sys.exc_info()
                try:
                    try:
                        if run_cleanup:
                            self._run_cleanup(args, dargs)
                    except Exception:
                        print 'Ignoring exception during cleanup() phase:'
                        traceback.print_exc()
                        print 'Now raising the earlier %s error' % exc_info[0]
                finally:
                    self.job.stderr.restore()
                    self.job.stdout.restore()
                    try:
                        raise exc_info[0], exc_info[1], exc_info[2]
                    finally:
                        # http://docs.python.org/library/sys.html#sys.exc_info
                        # Be nice and prevent a circular reference.
                        del exc_info
            else:
                try:
                    if run_cleanup:
                        self._run_cleanup(args, dargs)
                finally:
                    self.logger.removeHandler(self.test_handler)
                    self.job.stderr.restore()
                    self.job.stdout.restore()
        except error.AutotestError:
            # Pass already-categorized errors on up.
            raise
        except Exception, e:
            # Anything else is an ERROR in our own code, not execute().
            raise error.UnhandledTestError(e)


def _get_nonstar_args(func):
    """Extract all the (normal) function parameter names.

    Given a function, returns a tuple of parameter names, specifically
    excluding the * and ** parameters, if the function accepts them.

    @param func: A callable that we want to chose arguments for.

    @return: A tuple of parameters accepted by the function.
    """
    return func.func_code.co_varnames[:func.func_code.co_argcount]


def _cherry_pick_args(func, args, dargs):
    """Sanitize positional and keyword arguments before calling a function.

    Given a callable (func), an argument tuple and a dictionary of keyword
    arguments, pick only those arguments which the function is prepared to
    accept and return a new argument tuple and keyword argument dictionary.

    Args:
      func: A callable that we want to choose arguments for.
      args: A tuple of positional arguments to consider passing to func.
      dargs: A dictionary of keyword arguments to consider passing to func.
    Returns:
      A tuple of: (args tuple, keyword arguments dictionary)
    """
    # Cherry pick args:
    if func.func_code.co_flags & 0x04:
        # func accepts *args, so return the entire args.
        p_args = args
    else:
        p_args = ()

    # Cherry pick dargs:
    if func.func_code.co_flags & 0x08:
        # func accepts **dargs, so return the entire dargs.
        p_dargs = dargs
    else:
        # Only return the keyword arguments that func accepts.
        p_dargs = {}
        for param in _get_nonstar_args(func):
            if param in dargs:
                p_dargs[param] = dargs[param]

    return p_args, p_dargs


def _validate_args(args, dargs, *funcs):
    """Verify that arguments are appropriate for at least one callable.

    Given a list of callables as additional parameters, verify that
    the proposed keyword arguments in dargs will each be accepted by at least
    one of the callables.

    NOTE: args is currently not supported and must be empty.

    Args:
      args: A tuple of proposed positional arguments.
      dargs: A dictionary of proposed keyword arguments.
      *funcs: Callables to be searched for acceptance of args and dargs.
    Raises:
      error.AutotestError: if an arg won't be accepted by any of *funcs.
    """
    all_co_flags = 0
    all_varnames = ()
    for func in funcs:
        all_co_flags |= func.func_code.co_flags
        all_varnames += func.func_code.co_varnames[:func.func_code.co_argcount]

    # Check if given args belongs to at least one of the methods below.
    if len(args) > 0:
        # Current implementation doesn't allow the use of args.
        raise error.TestError('Unnamed arguments not accepted. Please '
                              'call job.run_test with named args only')

    # Check if given dargs belongs to at least one of the methods below.
    if len(dargs) > 0:
        if not all_co_flags & 0x08:
            # no func accepts *dargs, so:
            for param in dargs:
                if not param in all_varnames:
                    raise error.AutotestError('Unknown parameter: %s' % param)


def _installtest(job, url):
    (group, name) = job.pkgmgr.get_package_name(url, 'test')

    # Bail if the test is already installed
    group_dir = os.path.join(job.testdir, "download", group)
    if os.path.exists(os.path.join(group_dir, name)):
        return (group, name)

    # If the group directory is missing create it and add
    # an empty  __init__.py so that sub-directories are
    # considered for import.
    if not os.path.exists(group_dir):
        os.mkdir(group_dir)
        f = file(os.path.join(group_dir, '__init__.py'), 'w+')
        f.close()

    print name + ": installing test url=" + url
    tarball = os.path.basename(url)
    tarball_path = os.path.join(group_dir, tarball)
    test_dir = os.path.join(group_dir, name)
    job.pkgmgr.fetch_pkg(tarball, tarball_path,
                         repo_url = os.path.dirname(url))

    # Create the directory for the test
    if not os.path.exists(test_dir):
        os.mkdir(os.path.join(group_dir, name))

    job.pkgmgr.untar_pkg(tarball_path, test_dir)

    os.remove(tarball_path)

    # For this 'sub-object' to be importable via the name
    # 'group.name' we need to provide an __init__.py,
    # so link the main entry point to this.
    os.symlink(name + '.py', os.path.join(group_dir, name,
                            '__init__.py'))

    # The test is now installed.
    return (group, name)


def runtest(job, url, tag, args, dargs,
            local_namespace={}, global_namespace={},
            before_test_hook=None, after_test_hook=None):
    local_namespace = local_namespace.copy()
    global_namespace = global_namespace.copy()

    # if this is not a plain test name then download and install the
    # specified test
    if url.endswith('.tar.bz2'):
        (group, testname) = _installtest(job, url)
        bindir = os.path.join(job.testdir, 'download', group, testname)
        site_bindir = None
    else:
        # if the test is local, it can be found in either testdir
        # or site_testdir. tests in site_testdir override tests
        # defined in testdir
        (group, testname) = ('', url)
        bindir = os.path.join(job.testdir, group, testname)
        if hasattr(job, 'site_testdir'):
            site_bindir = os.path.join(job.site_testdir,
                                       group, testname)
        else:
            site_bindir = None

        # The job object here can be that of a server side job or a client
        # side job. 'install_pkg' method won't be present for server side
        # jobs, so do the fetch only if that method is present in the job
        # obj.
        if hasattr(job, 'install_pkg'):
            try:
                job.install_pkg(testname, 'test', bindir)
            except packages.PackageInstallError, e:
                # continue as a fall back mechanism and see if the test code
                # already exists on the machine
                pass

    outputdir = os.path.join(job.resultdir, testname)
    if tag:
        outputdir += '.' + tag

    # if we can find the test in site_bindir, use this version
    if site_bindir and os.path.exists(site_bindir):
        bindir = site_bindir
        testdir = job.site_testdir
    elif os.path.exists(bindir):
        testdir = job.testdir
    else:
        raise error.TestError(testname + ': test does not exist')

    local_namespace['job'] = job
    local_namespace['bindir'] = bindir
    local_namespace['outputdir'] = outputdir

    if group:
        sys.path.insert(0, os.path.join(testdir, 'download'))
        group += '.'
    else:
        sys.path.insert(0, os.path.join(testdir, testname))

    try:
        exec ("import %s%s" % (group, testname),
              local_namespace, global_namespace)
        exec ("mytest = %s%s.%s(job, bindir, outputdir)" %
              (group, testname, testname),
              local_namespace, global_namespace)
    finally:
        sys.path.pop(0)

    pwd = os.getcwd()
    os.chdir(outputdir)
    try:
        mytest = global_namespace['mytest']
        if before_test_hook:
            before_test_hook(mytest)
        mytest._exec(args, dargs)
    finally:
        os.chdir(pwd)
        if after_test_hook:
            after_test_hook(mytest)
        shutil.rmtree(mytest.tmpdir, ignore_errors=True)
