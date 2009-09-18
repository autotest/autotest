#!/usr/bin/python -u

import os, sys, unittest, optparse
import common
from autotest_lib.utils import parallel


parser = optparse.OptionParser()
parser.add_option("-r", action="store", type="string", dest="start",
                  default='',
                  help="root directory to start running unittests")
parser.add_option("--full", action="store_true", dest="full", default=False,
                  help="whether to run the shortened version of the test")
parser.add_option("--debug", action="store_true", dest="debug", default=False,
                  help="run in debug mode")

LONG_TESTS = set((
    'monitor_db_unittest.py',
    'barrier_unittest.py',
    'migrate_unittest.py',
    'frontend_unittest.py',
    'client_compilation_unittest.py',
    'csv_encoder_unittest.py',
    'rpc_interface_unittest.py',
    'logging_manager_test.py',
    'models_test.py',
    ))

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
    test = unittest.defaultTestLoader.loadTestsFromModule(mod)
    suite = unittest.TestSuite(test)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    if result.errors or result.failures:
        raise TestFailure(
                "%s had %d failures and %d errors." %
                ('.'.join(mod_names), len(result.failures), len(result.errors)))


def find_and_run_tests(start, options):
    """
    Find and run Python unittest suites below the given directory.  Only look
    in subdirectories of start that are actual importable Python modules.

    @param start: The absolute directory to look for tests under.
    @param options: optparse options.
    """
    modules = []

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
            if fname.endswith('_unittest.py') or fname.endswith('_test.py'):
                if not options.full and fname in LONG_TESTS:
                    continue
                path_no_py = os.path.join(dirpath, fname).rstrip('.py')
                assert path_no_py.startswith(ROOT)
                names = path_no_py[len(ROOT)+1:].split('/')
                modules.append(['autotest_lib'] + names)
                if options.debug:
                    print 'testing', path_no_py

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
        parser.error('Unexpected argument(s): %s' % args)
        parser.print_help()
        sys.exit(1)

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
