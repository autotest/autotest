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

import os, sys, re, fcntl, shutil, tarfile, time, warnings, tempfile

from autotest_lib.client.common_lib import error, utils, packages, debug
from autotest_lib.client.bin import autotest_utils


class base_test:
    preserve_srcdir = False

    def __init__(self, job, bindir, outputdir):
        self.job = job
        self.autodir = job.autodir

        self.outputdir = outputdir
        tagged_testname = os.path.basename(self.outputdir)
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
        self.tmpdir = tempfile.mkdtemp("_" + tagged_testname, dir=job.tmpdir)
        self.test_log = debug.get_logger(module='tests')


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
        print 'No initialize phase defined'
        pass


    def setup(self):
        pass


    def warmup(self, *args, **dargs):
        pass


    def execute(self, iterations=None, test_length=None, *args, **dargs):
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
        # and test_length), let's warn him
        if iterations and test_length:
            print 'Iterations parameter silently ignored (timed execution)'
        if test_length:
            test_start = time.time()
            time_elapsed = 0
            timed_counter = 0
            print 'Benchmark started. Minimum test length: %d s' % (test_length)
            while time_elapsed < test_length:
                timed_counter = timed_counter + 1
                if time_elapsed == 0:
                    print 'Executing iteration %d' % (timed_counter)
                elif time_elapsed > 0:
                    print 'Executing iteration %d, time_elapsed %d s' % \
                           (timed_counter, time_elapsed)
                self.run_once(*args, **dargs)
                test_iteration_finish = time.time()
                time_elapsed = test_iteration_finish - test_start
            print 'Benchmark finished after %d iterations' % (timed_counter)
            print 'Time elapsed: %d s' % (time_elapsed)
        else:
            if not iterations:
                iterations = 1
            # Dropped profilers.only() - if you want that, use iterations=0
            print 'Benchmark started. Number of iterations: %d' % (iterations)
            for self.iteration in range(1, iterations+1):
                print 'Executing iteration %d of %d' % (self.iteration,
                                                                    iterations)
                self.run_once(*args, **dargs)
            print 'Benchmark finished after %d iterations' % (iterations)

        # Do a profiling run if necessary
        if profilers.present():
            profilers.start(self)
            print 'Profilers present. Profiling run started'
            self.run_once(*args, **dargs)
            profilers.stop(self)
            profilers.report(self)

        # Do any postprocessing, normally extracting performance keyvals, etc
        self.postprocess()


    def postprocess(self):
        pass


    def cleanup(self):
        pass


    def _run_cleanup(self, exc_info, args, dargs):
        p_args, p_dargs = _cherry_pick_args(self.cleanup, args, dargs)

        # if an exception occurs during the cleanup() call, we
        # don't want it to override an existing exception
        # (i.e. exc_info) that was thrown by the test execution
        if exc_info:
            try:
                self.cleanup(*p_args, **p_dargs)
            finally:
                try:
                    raise exc_info[0], exc_info[1], exc_info[2]
                finally:
                    # necessary to prevent a circular reference
                    # between exc_info[2] (the traceback, which
                    # references all the exception stack frames)
                    # and this stack frame (which refs exc_info[2])
                    del exc_info
        else:
            self.cleanup(*p_args, **p_dargs)


    def _exec(self, args, dargs):
        self.job.stdout.tee_redirect(os.path.join(self.debugdir, 'stdout'))
        self.job.stderr.tee_redirect(os.path.join(self.debugdir, 'stderr'))

        try:
            # write out the test attributes into a keyval
            dargs   = dargs.copy()
            run_cleanup = dargs.pop('run_cleanup', self.job.run_test_cleanup)
            keyvals = dargs.pop('test_attributes', dict()).copy()
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
                if self.job.drop_caches:
                    print "Dropping caches before running test"
                    autotest_utils.drop_caches()

                os.chdir(self.outputdir)
                if hasattr(self, 'run_once'):
                    p_args, p_dargs = _cherry_pick_args(self.run_once,
                                                        args, dargs)
                    if 'iterations' in dargs:
                        p_dargs['iterations'] = dargs['iterations']
                    if 'test_length' in dargs:
                        p_dargs['test_length'] = dargs['test_length']
                else:
                    p_args, p_dargs = _cherry_pick_args(self.execute,
                                                        args, dargs)
                try:
                    self.execute(*p_args, **p_dargs)
                except error.AutotestError:
                    raise
                except Exception, e:
                    raise error.UnhandledTestFail(e)
            except:
                exc_info = sys.exc_info()
            else:
                exc_info = None

            # run the cleanup, and then restore the job.std* streams
            try:
                if run_cleanup:
                    self._run_cleanup(exc_info, args, dargs)
            finally:
                self.job.stderr.restore()
                self.job.stdout.restore()

        except error.AutotestError:
            raise
        except Exception, e:
            raise error.UnhandledTestError(e)


def _cherry_pick_args(func, args, dargs):
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
        p_dargs = {}
        for param in func.func_code.co_varnames[:func.func_code.co_argcount]:
            if param in dargs:
                p_dargs[param] = dargs[param]

    return p_args, p_dargs


def _validate_args(args, dargs, *funcs):
    all_co_flags = 0
    all_varnames = ()
    for func in funcs:
        all_co_flags |= func.func_code.co_flags
        all_varnames += func.func_code.co_varnames[:func.func_code.co_argcount]

    # Check if given args belongs to at least one of the methods below.
    if len(args) > 0:
        # Current implementation doesn't allow the use of args.
        raise error.AutotestError('Unnamed arguments not accepted. Please, ' \
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
