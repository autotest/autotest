#!/usr/bin/python -u

import os
import sys
import unittest
import optparse
import fcntl
try:
    import autotest.common as common
except ImportError:
    import common
from autotest.utils import parallel
from autotest.client.shared.test_utils import unittest as custom_unittest


class StreamProxy(object):

    """
    Mechanism to suppress stdout output, while keeping the original stdout.
    """

    def __init__(self, filename='/dev/null', stream=sys.stdout):
        """
        Keep 2 streams to write to, and eventually switch.
        """
        self.terminal = stream
        self.log = open(filename, "a")
        self.stream = self.log

    def write(self, message):
        """
        Write to the current stream.
        """
        self.stream.write(message)

    def flush(self):
        """
        Flush the current stream.
        """
        self.stream.flush()

    def switch(self):
        """
        Switch between the 2 currently available streams.
        """
        if self.stream == self.log:
            self.stream = self.terminal
        else:
            self.stream = self.log


def print_stdout(sr, end=True):
    try:
        sys.stdout.switch()
    except AttributeError:
        pass
    if end:
        print(sr)
    else:
        print(sr),
    try:
        sys.stdout.switch()
    except AttributeError:
        pass


class Bcolors(object):

    """
    Very simple class with color support.
    """

    def __init__(self):
        self.HEADER = '\033[94m'
        self.PASS = '\033[92m'
        self.SKIP = '\033[93m'
        self.FAIL = '\033[91m'
        self.ENDC = '\033[0m'
        allowed_terms = ['linux', 'xterm', 'xterm-256color', 'vt100']
        term = os.environ.get("TERM")
        if (not os.isatty(1)) or (not term in allowed_terms):
            self.disable()

    def disable(self):
        self.HEADER = ''
        self.PASS = ''
        self.SKIP = ''
        self.FAIL = ''
        self.ENDC = ''

# Instantiate bcolors to be used in the functions below.
bcolors = Bcolors()


def print_header(sr):
    """
    Print a string to stdout with HEADER (blue) color.
    """
    print_stdout(bcolors.HEADER + sr + bcolors.ENDC)


def print_skip():
    """
    Print SKIP to stdout with SKIP (yellow) color.
    """
    print_stdout(bcolors.SKIP + "SKIP" + bcolors.ENDC)


def print_pass(end=True):
    """
    Print PASS to stdout with PASS (green) color.
    """
    print_stdout(bcolors.PASS + "PASS" + bcolors.ENDC, end=end)


def print_fail(end=True):
    """
    Print FAIL to stdout with FAIL (red) color.
    """
    print_stdout(bcolors.FAIL + "FAIL" + bcolors.ENDC, end=end)


def silence_stderr():
    out_fd = os.open('/dev/null', os.O_WRONLY | os.O_CREAT)
    try:
        os.dup2(out_fd, 2)
    finally:
        os.close(out_fd)
    sys.stderr = os.fdopen(2, 'w')


parser = optparse.OptionParser()
parser.add_option("-r", action="store", type="string", dest="start",
                  default='',
                  help="root directory to start running unittests")
parser.add_option("--full", action="store_true", dest="full", default=False,
                  help="whether to run the shortened version of the test")
parser.add_option("--debug", action="store_true", dest="debug", default=False,
                  help="run in debug mode")
parser.add_option("--skip-tests", dest="skip_tests", default=[],
                  help="A space separated list of tests to skip")

parser.set_defaults(module_list=None)


REQUIRES_DJANGO = set((
    'monitor_db_unittest.py',
    'monitor_db_functional_unittest.py',
    'monitor_db_cleanup_unittest.py',
    'frontend_unittest.py',
    'csv_encoder_unittest.py',
    'rpc_interface_unittest.py',
    'models_unittest.py',
    'scheduler_models_unittest.py',
    'metahost_scheduler_unittest.py',
    'site_metahost_scheduler_unittest.py',
    'rpc_utils_unittest.py',
    'site_rpc_utils_unittest.py',
    'execution_engine_unittest.py',
    'service_proxy_lib_unittest.py',
    'reservations_unittest.py',
    'autotest_remote_unittest.py',
    'server_job_unittest.py',
))

REQUIRES_MYSQLDB = set((
    'migrate_unittest.py',
    'db_utils_unittest.py',
))

REQUIRES_GWT = set((
    'client_compilation_unittest.py',
))

REQUIRES_SIMPLEJSON = set((
    'resources_unittest.py',
    'serviceHandler_unittest.py',
))

REQUIRES_AUTH = set((
    'trigger_unittest.py',
))

REQUIRES_PROTOBUFS = set((
    'job_serializer_unittest.py',
))

REQUIRES_XML_ETREE = set((
    'autotest_firewalld_add_service_unittest.py',
))

LONG_RUNTIME = set((
    'base_barrier_unittest.py',
    'logging_manager_unittest.py',
    'base_syncdata_unittest.py'
))

LONG_TESTS = (REQUIRES_DJANGO |
              REQUIRES_MYSQLDB |
              REQUIRES_GWT |
              REQUIRES_SIMPLEJSON |
              REQUIRES_AUTH |
              REQUIRES_PROTOBUFS |
              REQUIRES_XML_ETREE |
              LONG_RUNTIME)


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))


class TestFailure(Exception):
    pass


def run_test(mod_names, options):
    """
    :param mod_names: A list of individual parts of the module name to import
            and run as a test suite.
    :param options: optparse options.
    """
    if not options.debug:
        sys.stdout = StreamProxy(stream=sys.stdout)
        silence_stderr()
    else:
        sys.stdout = StreamProxy(stream=sys.stdout)

    test_name = '.'.join(mod_names)
    fail = False

    try:
        mod = common.setup_modules.import_module(mod_names[-1],
                                                 '.'.join(mod_names[:-1]))
        for ut_module in [unittest, custom_unittest]:
            test = ut_module.defaultTestLoader.loadTestsFromModule(mod)
            suite = ut_module.TestSuite(test)
            runner = ut_module.TextTestRunner(verbosity=2)
            result = runner.run(suite)
            if result.errors or result.failures:
                fail = True
    except:
        fail = True

    lockfile = open('/var/tmp/unittest.lock', 'w')
    fcntl.flock(lockfile, fcntl.LOCK_EX)
    print_stdout(test_name + ":", end=False)
    if fail:
        print_fail()
    else:
        print_pass()
    fcntl.flock(lockfile, fcntl.LOCK_UN)
    lockfile.close()

    if fail:
        raise TestFailure("Test %s failed" % test_name)


def scan_for_modules(start, options):
    modules = []

    skip_tests = []
    if options.skip_tests:
        skip_tests = options.skip_tests.split()

    for dirpath, subdirs, filenames in os.walk(start):
        # Only look in and below subdirectories that are python modules.
        if '__init__.py' not in filenames:
            if options.full:
                for filename in filenames:
                    if filename.endswith('.pyc'):
                        os.unlink(os.path.join(dirpath, filename))
            # Skip all subdirectories below this one, it is not a module.
            del subdirs[:]
            if options.debug:
                print 'Skipping', dirpath
            continue  # Skip this directory.

        # Look for unittest files.
        for fname in filenames:
            if fname.endswith('_unittest.py'):
                if not options.full and fname in LONG_TESTS:
                    continue
                if fname[:-3] in skip_tests:
                    continue
                path_no_py = os.path.join(dirpath, fname).rstrip('.py')
                assert path_no_py.startswith(ROOT)
                names = path_no_py[len(ROOT) + 1:].split('/')
                modules.append(['autotest'] + names)
                if options.debug:
                    print 'testing', path_no_py
    return modules


def find_and_run_tests(start, options):
    """
    Find and run Python unittest suites below the given directory.  Only look
    in subdirectories of start that are actual importable Python modules.

    :param start: The absolute directory to look for tests under.
    :param options: optparse options.
    """
    if options.module_list:
        modules = []
        for m in options.module_list:
            modules.append(m.split('.'))
    else:
        modules = scan_for_modules(start, options)

    print_header('Number of test modules found: %d' % len(modules))

    functions = {}
    for module_names in modules:
        # Create a function that'll test a particular module.  module=module
        # is a hack to force python to evaluate the params now.  We then
        # rename the function to make error reporting nicer.
        run_module = lambda module=module_names: run_test(module, options)
        name = '.'.join(module_names)
        run_module.__name__ = name
        functions[run_module] = set()

    try:
        dargs = {}
        if options.debug:
            dargs['max_simultaneous_procs'] = 1
        pe = parallel.ParallelExecute(functions, **dargs)
        pe.run_until_completion()
    except parallel.ParallelError, err:
        return err.errors
    return []


def main():
    options, args = parser.parse_args()
    if args:
        options.module_list = args

    # Strip the arguments off the command line, so that the unit tests do not
    # see them.
    del sys.argv[1:]

    absolute_start = os.path.join(ROOT, options.start)
    errors = find_and_run_tests(absolute_start, options)
    if errors:
        print "%d tests resulted in an error/failure:" % len(errors)
        for error in errors:
            print "\t%s" % error
        print "Rerun", sys.argv[0], "--debug to see the failure details."
        sys.exit(1)
    else:
        print "All passed!"
        sys.exit(0)


if __name__ == "__main__":
    main()
