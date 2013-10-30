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

import fcntl
import getpass
import os
import re
import sys
import shutil
import tempfile
import time
import traceback
import logging

from autotest.client.shared import error, utils_memory
from autotest.client.shared.settings import settings
from autotest.client import utils


class base_test(object):
    preserve_srcdir = False
    network_destabilizing = False

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
        if getpass.getuser() == 'root':
            self.configure_crash_handler()
        else:
            self.crash_handling_enabled = False
        self.bindir = bindir
        try:
            autodir = os.path.abspath(os.environ['AUTODIR'])
        except KeyError:
            autodir = settings.get_value('COMMON', 'autotest_top_path')
        tmpdir = os.path.join(autodir, 'tmp')
        output_config = settings.get_value('COMMON', 'test_output_dir',
                                           default=tmpdir)
        self.srcdir = os.path.join(output_config, os.path.basename(self.bindir),
                                   'src')
        self.tmpdir = tempfile.mkdtemp("_" + self.tagged_testname,
                                       dir=job.tmpdir)
        self._keyvals = []
        self._new_keyval = False
        self.failed_constraints = []
        self.iteration = 0
        self.before_iteration_hooks = []
        self.after_iteration_hooks = []

    def configure_crash_handler(self):
        pass

    def crash_handler_report(self):
        pass

    def assert_(self, expr, msg='Assertion failed.'):
        if not expr:
            raise error.TestError(msg)

    def write_test_keyval(self, attr_dict):
        utils.write_keyval(self.outputdir, attr_dict,
                           tap_report=self.job._tap)

    @staticmethod
    def _append_type_to_keys(dictionary, typename):
        new_dict = {}
        for key, value in dictionary.iteritems():
            new_key = "%s{%s}" % (key, typename)
            new_dict[new_key] = value
        return new_dict

    def write_perf_keyval(self, perf_dict):
        self.write_iteration_keyval({}, perf_dict,
                                    tap_report=self.job._tap)

    def write_attr_keyval(self, attr_dict):
        self.write_iteration_keyval(attr_dict, {},
                                    tap_report=self.job._tap)

    def write_iteration_keyval(self, attr_dict, perf_dict, tap_report=None):
        # append the dictionaries before they have the {perf} and {attr} added
        self._keyvals.append({'attr': attr_dict, 'perf': perf_dict})
        self._new_keyval = True

        if attr_dict:
            attr_dict = self._append_type_to_keys(attr_dict, "attr")
            utils.write_keyval(self.resultsdir, attr_dict, type_tag="attr",
                               tap_report=tap_report)

        if perf_dict:
            perf_dict = self._append_type_to_keys(perf_dict, "perf")
            utils.write_keyval(self.resultsdir, perf_dict, type_tag="perf",
                               tap_report=tap_report)

        keyval_path = os.path.join(self.resultsdir, "keyval")
        print >> open(keyval_path, "a"), ""

    def analyze_perf_constraints(self, constraints):
        if not self._new_keyval:
            return

        # create a dict from the keyvals suitable as an environment for eval
        keyval_env = self._keyvals[-1]['perf'].copy()
        keyval_env['__builtins__'] = None
        self._new_keyval = False
        failures = []

        # evaluate each constraint using the current keyvals
        for constraint in constraints:
            logging.info('___________________ constraint = %s', constraint)
            logging.info('___________________ keyvals = %s', keyval_env)

            try:
                if not eval(constraint, keyval_env):
                    failures.append('%s: constraint was not met' % constraint)
            except Exception:
                failures.append('could not evaluate constraint: %s'
                                % constraint)

        # keep track of the errors for each iteration
        self.failed_constraints.append(failures)

    def process_failed_constraints(self):
        msg = ''
        for i, failures in enumerate(self.failed_constraints):
            if failures:
                msg += 'iteration %d:%s  ' % (i, ','.join(failures))

        if msg:
            raise error.TestFail(msg)

    def register_before_iteration_hook(self, iteration_hook):
        """
        This is how we expect test writers to register a before_iteration_hook.
        This adds the method to the list of hooks which are executed
        before each iteration.

        @param iteration_hook: Method to run before each iteration. A valid
                               hook accepts a single argument which is the
                               test object.
        """
        self.before_iteration_hooks.append(iteration_hook)

    def register_after_iteration_hook(self, iteration_hook):
        """
        This is how we expect test writers to register an after_iteration_hook.
        This adds the method to the list of hooks which are executed
        after each iteration.

        @param iteration_hook: Method to run after each iteration. A valid
                               hook accepts a single argument which is the
                               test object.
        """
        self.after_iteration_hooks.append(iteration_hook)

    def initialize(self):
        pass

    def setup(self):
        pass

    def warmup(self, *args, **dargs):
        pass

    def drop_caches_between_iterations(self):
        if self.job.drop_caches_between_iterations:
            utils_memory.drop_caches()

    def _call_run_once(self, constraints, profile_only,
                       postprocess_profiled_run, args, dargs):
        self.drop_caches_between_iterations()

        # execute iteration hooks
        for hook in self.before_iteration_hooks:
            hook(self)

        try:
            if profile_only:
                if not self.job.profilers.present():
                    self.job.record('WARN', None, None,
                                    'No profilers have been added but '
                                    'profile_only is set - nothing '
                                    'will be run')
                self.run_once_profiling(postprocess_profiled_run,
                                        *args, **dargs)
            else:
                self.before_run_once()
                self.run_once(*args, **dargs)
                self.after_run_once()

            self.postprocess_iteration()
            self.analyze_perf_constraints(constraints)
        finally:
            for hook in self.after_iteration_hooks:
                hook(self)

    def execute(self, iterations=None, test_length=None, profile_only=None,
                _get_time=time.time, postprocess_profiled_run=None,
                constraints=(), *args, **dargs):
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

        @param profile_only: If true run X iterations with profilers enabled.
            If false run X iterations and one with profiling if profiles are
            enabled. If None, default to the value of job.default_profile_only.

        @param _get_time: [time.time] Used for unit test time injection.

        @param postprocess_profiled_run: Run the postprocessing for the
            profiled run.
        """

        # For our special class of tests, the benchmarks, we don't want
        # profilers to run during the test iterations. Let's reserve only
        # the last iteration for profiling, if needed. So let's stop
        # all profilers if they are present and active.
        profilers = self.job.profilers
        if profilers.active():
            profilers.stop(self)
        if profile_only is None:
            profile_only = self.job.default_profile_only
        # If the user called this test in an odd way (specified both iterations
        # and test_length), let's warn them.
        if iterations and test_length:
            logging.debug('Iterations parameter ignored (timed execution)')
        if test_length:
            test_start = _get_time()
            time_elapsed = 0
            timed_counter = 0
            logging.debug('Test started. Specified %d s as the minimum test '
                          'length', test_length)
            while time_elapsed < test_length:
                timed_counter = timed_counter + 1
                if time_elapsed == 0:
                    logging.debug('Executing iteration %d', timed_counter)
                elif time_elapsed > 0:
                    logging.debug('Executing iteration %d, time_elapsed %d s',
                                  timed_counter, time_elapsed)
                self._call_run_once(constraints, profile_only,
                                    postprocess_profiled_run, args, dargs)
                test_iteration_finish = _get_time()
                time_elapsed = test_iteration_finish - test_start
            logging.debug('Test finished after %d iterations, '
                          'time elapsed: %d s', timed_counter, time_elapsed)
        else:
            if iterations is None:
                iterations = 1
            if iterations > 1:
                logging.debug('Test started. Specified %d iterations',
                              iterations)
            for self.iteration in xrange(1, iterations + 1):
                if iterations > 1:
                    logging.debug('Executing iteration %d of %d',
                                  self.iteration, iterations)
                self._call_run_once(constraints, profile_only,
                                    postprocess_profiled_run, args, dargs)

        if not profile_only:
            self.iteration += 1
            self.run_once_profiling(postprocess_profiled_run, *args, **dargs)

        # Do any postprocessing, normally extracting performance keyvals, etc
        self.postprocess()
        self.process_failed_constraints()

    def run_once_profiling(self, postprocess_profiled_run, *args, **dargs):
        profilers = self.job.profilers
        # Do a profiling run if necessary
        if profilers.present():
            self.drop_caches_between_iterations()
            profilers.before_start(self)

            self.before_run_once()
            profilers.start(self)
            logging.debug('Profilers present. Profiling run started')

            try:
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

            self.after_run_once()

    def postprocess(self):
        pass

    def postprocess_iteration(self):
        pass

    def cleanup(self):
        pass

    def before_run_once(self):
        """
        Override in tests that need it, will be called before any run_once()
        call including the profiling run (when it's called before starting
        the profilers).
        """
        pass

    def after_run_once(self):
        """
        Called after every run_once (including from a profiled run when it's
        called after stopping the profilers).
        """
        pass

    def _exec(self, args, dargs):
        self.job.logging.tee_redirect_debug_dir(self.debugdir,
                                                log_name=self.tagged_testname)
        try:
            if self.network_destabilizing:
                self.job.disable_warnings("NETWORK")

            # write out the test attributes into a keyval
            dargs = dargs.copy()
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
                _cherry_pick_call(self.initialize, *args, **dargs)

                lockfile = open(os.path.join(self.job.tmpdir, '.testlock'), 'w')
                try:
                    fcntl.flock(lockfile, fcntl.LOCK_EX)
                    # Setup: (compile and install the test, if needed)
                    p_args, p_dargs = _cherry_pick_args(self.setup, args, dargs)
                    utils.update_version(self.srcdir, self.preserve_srcdir,
                                         self.version, self.setup,
                                         *p_args, **p_dargs)
                finally:
                    fcntl.flock(lockfile, fcntl.LOCK_UN)
                    lockfile.close()

                # Execute:
                os.chdir(self.outputdir)

                # call self.warmup cherry picking the arguments it accepts and
                # translate exceptions if needed
                _call_test_function(_cherry_pick_call, self.warmup,
                                    *args, **dargs)

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

                _call_test_function(self.execute, *p_args, **p_dargs)
            except Exception:
                try:
                    logging.exception('Exception escaping from test:')
                except:
                    pass  # don't let logging exceptions here interfere

                # Save the exception while we run our cleanup() before
                # reraising it.
                exc_info = sys.exc_info()
                try:
                    try:
                        if run_cleanup:
                            _cherry_pick_call(self.cleanup, *args, **dargs)
                    except Exception:
                        logging.error('Ignoring exception during cleanup() phase:')
                        traceback.print_exc()
                        logging.error('Now raising the earlier %s error',
                                      exc_info[0])
                    self.crash_handler_report()
                finally:
                    self.job.logging.restore()
                    try:
                        raise exc_info[0], exc_info[1], exc_info[2]
                    finally:
                        # http://docs.python.org/library/sys.html#sys.exc_info
                        # Be nice and prevent a circular reference.
                        del exc_info
            else:
                try:
                    if run_cleanup:
                        _cherry_pick_call(self.cleanup, *args, **dargs)
                    self.crash_handler_report()
                finally:
                    self.job.logging.restore()
        except error.AutotestError:
            if self.network_destabilizing:
                self.job.enable_warnings("NETWORK")
            # Pass already-categorized errors on up.
            raise
        except Exception, e:
            if self.network_destabilizing:
                self.job.enable_warnings("NETWORK")
            # Anything else is an ERROR in our own code, not execute().
            raise error.UnhandledTestError(e)
        else:
            if self.network_destabilizing:
                self.job.enable_warnings("NETWORK")


def subtest_fatal(function):
    """
    Decorator which mark test critical.
    If subtest fails the whole test ends.
    """

    def wrapped(self, *args, **kwds):
        self._fatal = True
        self.decored()
        result = function(self, *args, **kwds)
        return result
    wrapped.func_name = function.func_name
    return wrapped


def subtest_nocleanup(function):
    """
    Decorator used to disable cleanup function.
    """

    def wrapped(self, *args, **kwds):
        self._cleanup = False
        self.decored()
        result = function(self, *args, **kwds)
        return result
    wrapped.func_name = function.func_name
    return wrapped


class Subtest(object):

    """
    Collect result of subtest of main test.
    """
    result = []
    passed = 0
    failed = 0

    def __new__(cls, *args, **kargs):
        self = super(Subtest, cls).__new__(cls)

        self._fatal = False
        self._cleanup = True
        self._num_decored = 0

        ret = None
        if args is None:
            args = []

        res = {
            'result': None,
            'name': self.__class__.__name__,
            'args': args,
            'kargs': kargs,
            'output': None,
        }
        try:
            try:
                logging.info("Starting test %s" % self.__class__.__name__)
                ret = self.test(*args, **kargs)
                res['result'] = 'PASS'
                res['output'] = ret
                try:
                    logging.info(Subtest.result_to_string(res))
                except:
                    self._num_decored = 0
                    raise
                Subtest.result.append(res)
                Subtest.passed += 1
            except NotImplementedError:
                raise
            except Exception:
                exc_type, exc_value, exc_traceback = sys.exc_info()
                for _ in range(self._num_decored):
                    exc_traceback = exc_traceback.tb_next
                logging.error("In function (" + self.__class__.__name__ + "):")
                logging.error("Call from:\n" +
                              traceback.format_stack()[-2][:-1])
                logging.error("Exception from:\n" +
                              "".join(traceback.format_exception(
                                      exc_type, exc_value,
                                      exc_traceback.tb_next)))
                # Clean up environment after subTest crash
                res['result'] = 'FAIL'
                logging.info(self.result_to_string(res))
                Subtest.result.append(res)
                Subtest.failed += 1
                if self._fatal:
                    raise
        finally:
            if self._cleanup:
                self.clean()

        return ret

    def test(self):
        """
        Check if test is defined.

        For makes test fatal add before implementation of test method
        decorator @subtest_fatal
        """
        raise NotImplementedError("Method 'test' must be implemented.")

    def clean(self):
        """
        Check if cleanup is defined.

        For makes test fatal add before implementation of test method
        decorator @subtest_nocleanup
        """
        raise NotImplementedError("Method 'cleanup' must be implemented.")

    def decored(self):
        self._num_decored += 1

    @classmethod
    def has_failed(cls):
        """
        :return: If any of subtest not pass return True.
        """
        if cls.failed > 0:
            return True
        else:
            return False

    @classmethod
    def get_result(cls):
        """
        :return: Result of subtests.
           Format:
             tuple(pass/fail,function_name,call_arguments)
        """
        return cls.result

    @staticmethod
    def result_to_string_debug(result):
        """
        @param result: Result of test.
        """
        sargs = ""
        for arg in result['args']:
            sargs += str(arg) + ","
        sargs = sargs[:-1]
        return ("Subtest (%s(%s)): --> %s") % (result['name'],
                                               sargs,
                                               result['status'])

    @staticmethod
    def result_to_string(result):
        """
        Format of result dict.

        result = {
               'result' : "PASS" / "FAIL",
               'name'   : class name,
               'args'   : test's args,
               'kargs'  : test's kargs,
               'output' : return of test function,
              }

        @param result: Result of test.
        """
        return ("Subtest (%(name)s): --> %(result)s") % (result)

    @classmethod
    def log_append(cls, msg):
        """
        Add log_append to result output.

        @param msg: Test of log_append
        """
        cls.result.append([msg])

    @classmethod
    def _gen_res(cls, format_func):
        """
        Format result with formatting function

        @param format_func: Func for formating result.
        """
        result = ""
        for res in cls.result:
            if (isinstance(res, dict)):
                result += format_func(res) + "\n"
            else:
                result += str(res[0]) + "\n"
        return result

    @classmethod
    def get_full_text_result(cls, format_func=None):
        """
        :return: string with text form of result
        """
        if format_func is None:
            format_func = cls.result_to_string_debug
        return cls._gen_res(lambda s: format_func(s))

    @classmethod
    def get_text_result(cls, format_func=None):
        """
        :return: string with text form of result
        """
        if format_func is None:
            format_func = cls.result_to_string
        return cls._gen_res(lambda s: format_func(s))

    def runsubtest(self, url, *args, **dargs):
        """
        Execute another autotest test from inside the current test's scope.

        @param test: Parent test.
        @param url: Url of new test.
        @param tag: Tag added to test name.
        @param args: Args for subtest.
        @param dargs: Dictionary with args for subtest.
        @iterations: Number of subtest iterations.
        @profile_only: If true execute one profiled run.
        """
        dargs["profile_only"] = dargs.get("profile_only", False)
        test_basepath = self.outputdir[len(self.job.resultdir + "/"):]
        return self.job.run_test(url, master_testpath=test_basepath,
                                 *args, **dargs)


def _get_nonstar_args(func):
    """Extract all the (normal) function parameter names.

    Given a function, returns a tuple of parameter names, specifically
    excluding the * and ** parameters, if the function accepts them.

    @param func: A callable that we want to chose arguments for.

    :return: A tuple of parameters accepted by the function.
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


def _cherry_pick_call(func, *args, **dargs):
    """Cherry picks arguments from args/dargs based on what "func" accepts
    and calls the function with the picked arguments."""
    p_args, p_dargs = _cherry_pick_args(func, args, dargs)
    return func(*p_args, **p_dargs)


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
        os.makedirs(group_dir)
        f = file(os.path.join(group_dir, '__init__.py'), 'w+')
        f.close()

    logging.debug("%s: installing test url=%s", name, url)
    tarball = os.path.basename(url)
    tarball_path = os.path.join(group_dir, tarball)
    test_dir = os.path.join(group_dir, name)
    job.pkgmgr.fetch_pkg(tarball, tarball_path,
                         repo_url=os.path.dirname(url))

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


def _call_test_function(func, *args, **dargs):
    """Calls a test function and translates exceptions so that errors
    inside test code are considered test failures."""
    try:
        return func(*args, **dargs)
    except error.AutotestError:
        # Pass already-categorized errors on up as is.
        raise
    except Exception, e:
        # Other exceptions must be treated as a FAIL when
        # raised during the test functions
        raise error.UnhandledTestFail(e)


def runtest(job, url, tag, args, dargs,
            local_namespace={}, global_namespace={},
            before_test_hook=None, after_test_hook=None,
            before_iteration_hook=None, after_iteration_hook=None):
    local_namespace = local_namespace.copy()
    global_namespace = global_namespace.copy()

    # if this is not a plain test name then download and install the
    # specified test
    if url.endswith('.tar.bz2'):
        (testgroup, testname) = _installtest(job, url)
        bindir = os.path.join(job.testdir, 'download', testgroup, testname)
        importdir = os.path.join(job.testdir, 'download')
        modulename = '%s.%s' % (re.sub('/', '.', testgroup), testname)
        classname = '%s.%s' % (modulename, testname)
        path = testname
    else:
        # If the test is local, it may be under either testdir or site_testdir.
        # Tests in site_testdir override tests defined in testdir
        testname = path = url
        testgroup = ''
        path = re.sub(':', '/', testname)
        modulename = os.path.basename(path)
        classname = '%s.%s' % (modulename, modulename)

        # Try installing the test package
        # The job object may be either a server side job or a client side job.
        # 'install_pkg' method will be present only if it's a client side job.
        if hasattr(job, 'install_pkg'):
            try:
                bindir = os.path.join(job.site_testdir, testname)
                job.install_pkg(testname, 'test', bindir)
            except error.PackageInstallError:
                # continue as a fall back mechanism and see if the test code
                # already exists on the machine
                pass

        testdir_list = [job.testdir, getattr(job, 'site_testdir', None), job.customtestdir]
        bindir_config = settings.get_value('COMMON', 'test_dir', default="")
        if bindir_config:
            testdir_list.extend(bindir_config.strip().split(','))

        bindir = None
        for t_dir in testdir_list:
            if t_dir is not None and os.path.exists(os.path.join(t_dir, path)):
                importdir = bindir = os.path.join(t_dir, path)
        if not bindir:
            raise error.TestError(testname + ': test does not exist')

    subdir = os.path.join(dargs.pop('master_testpath', ""), testname)
    outputdir = os.path.join(job.resultdir, subdir)
    if tag:
        outputdir += '.' + tag

    local_namespace['job'] = job
    local_namespace['outputdir'] = outputdir
    local_namespace['bindir'] = bindir

    sys.path.insert(0, importdir)
    try:
        exec ('import %s' % modulename, local_namespace, global_namespace)
        exec ("mytest = %s(job, bindir, outputdir)" % classname,
              local_namespace, global_namespace)
    finally:
        sys.path.pop(0)

    pwd = os.getcwd()
    os.chdir(outputdir)

    try:
        mytest = global_namespace['mytest']
        if before_test_hook:
            before_test_hook(mytest)

        # we use the register iteration hooks methods to register the passed
        # in hooks
        if before_iteration_hook:
            mytest.register_before_iteration_hook(before_iteration_hook)
        if after_iteration_hook:
            mytest.register_after_iteration_hook(after_iteration_hook)
        mytest._exec(args, dargs)
    finally:
        os.chdir(pwd)
        if after_test_hook:
            after_test_hook(mytest)
        shutil.rmtree(mytest.tmpdir, ignore_errors=True)
