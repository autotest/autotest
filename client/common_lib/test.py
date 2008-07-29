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
#       tmpdir          eg. tmp/<testname.tag>

import os, sys, re, fcntl, shutil, tarfile, warnings

from autotest_lib.client.common_lib import error, utils


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

        self.tmpdir = os.path.join(job.tmpdir, tagged_testname)

        if os.path.exists(self.tmpdir):
            shutil.rmtree(self.tmpdir)
        os.mkdir(self.tmpdir)


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


    def execute(self, iterations=1, *args, **dargs):
        self.warmup(*args, **dargs)

        profilers = self.job.profilers
        # Dropped profilers.only() - if you want that, use iterations=0
        for i in range(iterations):
            self.run_once(*args, **dargs)

        # Do a profiling run if necessary
        if profilers.present():
            profilers.start(self)
            self.run_once(*args, **dargs)
            profilers.stop(self)
            profilers.report(self)

        # Do any postprocessing, normally extracting performance keyvals, etc
        self.postprocess()


    def postprocess(self):
        pass


    def cleanup(self):
        pass


    def _exec(self, args, dargs):
        self.job.stdout.tee_redirect(os.path.join(self.debugdir, 'stdout'))
        self.job.stderr.tee_redirect(os.path.join(self.debugdir, 'stderr'))

        try:
            # write out the test attributes into a keyval
            dargs   = dargs.copy()
            keyvals = dargs.pop('test_attributes', dict()).copy()
            keyvals['version'] = self.version
            self.write_test_keyval(keyvals)

            _validate_args(args, dargs, self.initialize, self.setup,
                           self.execute, self.cleanup)

            try:
                # Initialize:
                p_args, p_dargs = _cherry_pick_args(self.initialize,args,dargs)
                self.initialize(*p_args, **p_dargs)

                # Setup: (compile and install the test, if needed)
                p_args, p_dargs = _cherry_pick_args(self.setup,args,dargs)
                utils.update_version(self.srcdir, self.preserve_srcdir,
                                     self.version, self.setup,
                                     *p_args, **p_dargs)

                # Execute:
                os.chdir(self.outputdir)
                if hasattr(self, 'run_once'):
                    p_args, p_dargs = _cherry_pick_args(self.run_once,
                                                        args, dargs)
                    if 'iterations' in dargs:
                        p_dargs['iterations'] = dargs['iterations']
                else:
                    p_args, p_dargs = _cherry_pick_args(self.execute,
                                                        args, dargs)
                try:
                    self.execute(*p_args, **p_dargs)
                except error.AutotestError:
                    raise
                except Exception, e:
                    raise error.UnhandledTestFail(e)

            finally:
                self.cleanup()
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


def testname(url):
    # Extract the testname from the test url.
    match = re.match('[^:]+://(.*)/([^/]*)$', url)
    if not match:
        return ('', url)
    (group, filename) = match.groups()

    # Generate the group prefix.
    group = re.sub(r'\W', '_', group)

    # Drop the extension to get the raw test name.
    testname = re.sub(r'\.tgz', '', filename)

    return (group, testname)


def _installtest(job, url):
    (group, name) = testname(url)

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
    utils.get_file(url, os.path.join(group_dir, 'test.tgz'))
    old_wd = os.getcwd()
    os.chdir(group_dir)
    tar = tarfile.open('test.tgz')
    for member in tar.getmembers():
        tar.extract(member)
    tar.close()
    os.chdir(old_wd)
    os.remove(os.path.join(group_dir, 'test.tgz'))

    # For this 'sub-object' to be importable via the name
    # 'group.name' we need to provide an __init__.py,
    # so link the main entry point to this.
    os.symlink(name + '.py', os.path.join(group_dir, name,
                            '__init__.py'))

    # The test is now installed.
    return (group, name)


def runtest(job, url, tag, args, dargs,
            local_namespace={}, global_namespace={}, after_test_hook=None):
    local_namespace = local_namespace.copy()
    global_namespace = global_namespace.copy()

    # if this is not a plain test name then download and install the
    # specified test
    if utils.is_url(url):
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

    outputdir = os.path.join(job.resultdir, testname)
    if tag:
        outputdir += '.' + tag

    # if we can find the test in site_bindir, use this version
    if site_bindir and os.path.exists(site_bindir):
        bindir = site_bindir
        testdir = job.site_testdir
    elif os.path.exists(bindir):
        testdir = job.testdir
    elif not os.path.exists(bindir):
        raise error.TestError(testname + ': test does not exist')

    if group:
        sys.path.insert(0, os.path.join(testdir, 'download'))
        group += '.'
    else:
        sys.path.insert(0, os.path.join(testdir, testname))

    local_namespace['job'] = job
    local_namespace['bindir'] = bindir
    local_namespace['outputdir'] = outputdir

    lockfile = open(os.path.join(job.tmpdir, '.testlock'), 'w')
    try:
        fcntl.flock(lockfile, fcntl.LOCK_EX)
        exec ("import %s%s" % (group, testname),
              local_namespace, global_namespace)
        exec ("mytest = %s%s.%s(job, bindir, outputdir)" %
              (group, testname, testname),
              local_namespace, global_namespace)
    finally:
        fcntl.flock(lockfile, fcntl.LOCK_UN)
        lockfile.close()
        sys.path.pop(0)

    pwd = os.getcwd()
    os.chdir(outputdir)
    try:
        mytest = global_namespace['mytest']
        mytest._exec(args, dargs)
    finally:
        if after_test_hook:
            after_test_hook(mytest)
