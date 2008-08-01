#!/usr/bin/python -u

import os, sys, unittest, optparse
import common
from autotest_lib.utils import parallel


debug = False
root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

parser = optparse.OptionParser()
parser.add_option("-r", action="store", type="string", dest="start",
                  default='',
                  help="root directory to start running unittests")
parser.add_option("--full", action="store_true", dest="full", default=False,
                  help="whether to run the shortened version of the test")


LONG_TESTS = set((
    'monitor_db_unittest.py',
    'barrier_unittest.py',
    'migrate_unittest.py',
    'frontend_unittest.py',
    ))

modules = []


def lister(full, dirname, files):
    for f in files:
        if f.endswith('_unittest.py'):
            if not full and f in LONG_TESTS:
                continue
            temp = os.path.join(dirname, f).strip('.py')
            mod_name = ['autotest_lib'] + temp[len(root)+1:].split('/')
            modules.append(mod_name)


def run_test(mod_name):
    if not debug:
        parallel.redirect_io()

    print "Running %s" % '.'.join(mod_name)
    mod = common.setup_modules.import_module(mod_name[-1],
                                             '.'.join(mod_name[:-1]))
    test = unittest.defaultTestLoader.loadTestsFromModule(mod)
    suite = unittest.TestSuite(test)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    if result.errors or result.failures:
        raise Exception("%s failed" % '.'.join(mod_name))


def run_tests(start, full=False):
    os.path.walk(start, lister, full)

    functions = []
    for module in modules:
        # Create a function that'll test a particular module.  module=module
        # is a hack to force python to evaluate the params now.  We then
        # rename the function to make error reporting nicer.
        run_module = lambda module=module: run_test(module)
        run_module.__name__ = '.'.join(module)
        functions.append(run_module)

    try:
        dargs = {}
        if debug:
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

    errors = run_tests(os.path.join(root, options.start), options.full)
    if errors:
        print "%d tests resulted in an error/failure:" % len(errors)
        for error in errors:
            print "\t%s" % error
        sys.exit(1)
    else:
        print "All passed!"
        sys.exit(0)

if __name__ == "__main__":
    main()
