#!/usr/bin/python -u

import os, sys, unittest, optparse
try:
    import autotest.common as common
except ImportError:
    import common
from autotest.utils import parallel
from autotest.client.shared.test_utils import unittest as custom_unittest

parser = optparse.OptionParser()
parser.add_option("-r", action="store", type="string", dest="start",
                  default='',
                  help="root directory to start running unittests")
parser.add_option("--full", action="store_true", dest="full", default=False,
                  help="whether to run the shortened version of the test")
parser.add_option("--debug", action="store_true", dest="debug", default=False,
                  help="run in debug mode")
parser.add_option("--skip-tests", dest="skip_tests",  default=[],
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

REQUIRES_AUTH = set ((
    'trigger_unittest.py',
    ))

REQUIRES_PROTOBUFS = set((
        'job_serializer_unittest.py',
        ))

LONG_RUNTIME = set((
    'base_barrier_unittest.py',
    'logging_manager_unittest.py',
    ))

LONG_TESTS = (REQUIRES_DJANGO |
              REQUIRES_MYSQLDB |
              REQUIRES_GWT |
              REQUIRES_SIMPLEJSON |
              REQUIRES_AUTH |
              REQUIRES_PROTOBUFS |
              LONG_RUNTIME)


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))


class TestFailure(Exception): pass


def run_test(mod_names, options):
    """
    @param mod_names: A list of individual parts of the module name to import
            and run as a test suite.
    @param options: optparse options.
    """
    if not options.debug:
        parallel.redirect_io()

    print "Running %s" % '.'.join(mod_names)
    mod = common.setup_modules.import_module(mod_names[-1],
                                             '.'.join(mod_names[:-1]))
    for ut_module in [unittest, custom_unittest]:
        test = ut_module.defaultTestLoader.loadTestsFromModule(mod)
        suite = ut_module.TestSuite(test)
        runner = ut_module.TextTestRunner(verbosity=2)
        result = runner.run(suite)
        if result.errors or result.failures:
            msg = '%s had %d failures and %d errors.'
            msg %= '.'.join(mod_names), len(result.failures), len(result.errors)
            raise TestFailure(msg)


def scan_for_modules(start, options):
    modules = []

    skip_tests = []
    if options.skip_tests:
        skip_tests.update(options.skip_tests.split())

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
                if fname in skip_tests:
                    continue
                path_no_py = os.path.join(dirpath, fname).rstrip('.py')
                assert path_no_py.startswith(ROOT)
                names = path_no_py[len(ROOT)+1:].split('/')
                modules.append(['autotest'] + names)
                if options.debug:
                    print 'testing', path_no_py
    return modules

def find_and_run_tests(start, options):
    """
    Find and run Python unittest suites below the given directory.  Only look
    in subdirectories of start that are actual importable Python modules.

    @param start: The absolute directory to look for tests under.
    @param options: optparse options.
    """
    if options.module_list:
        modules = []
        for m in options.module_list:
            modules.append(m.split('.'))
    else:
        modules = scan_for_modules(start, options)

    if options.debug:
        print 'Number of test modules found:', len(modules)

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
