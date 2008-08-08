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

DEPENDENCIES = {
    # Annotate dependencies here. The format is
    # module: [list of modules on which it is dependent]
    # (All modules in the list must run before this module can)

    # Note: Do not make a short test dependent on a long one. This will cause
    # the suite to fail if it is run without the --full flag, since the module
    # that the short test depends on will not be run.


    # The next two dependencies are not really dependencies. This is actually a
    # hack to keep these three modules from running at the same time, since they
    # all create and destroy a database with the same name.
    'autotest_lib.frontend.frontend_unittest':
        ['autotest_lib.migrate.migrate_unittest'],

    'autotest_lib.scheduler.monitor_db_unittest':
        ['autotest_lib.frontend.frontend_unittest',
         'autotest_lib.migrate.migrate_unittest'],
}

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

    functions = {}
    names_to_functions = {}
    for module in modules:
        # Create a function that'll test a particular module.  module=module
        # is a hack to force python to evaluate the params now.  We then
        # rename the function to make error reporting nicer.
        run_module = lambda module=module: run_test(module)
        name = '.'.join(module)
        run_module.__name__ = name
        names_to_functions[name] = run_module
        functions[run_module] = set()

    for fn, deps in DEPENDENCIES.iteritems():
        if fn in names_to_functions:
            functions[names_to_functions[fn]] = set(
                names_to_functions[dep] for dep in deps)

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

    # Strip the arguments off the command line, so that the unit tests do not
    # see them.
    sys.argv = [sys.argv[0]]

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
