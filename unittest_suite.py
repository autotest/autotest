#!/usr/bin/python

import os, sys, unittest
import common


LONG_TESTS = set((
    'monitor_db_unittest.py',
    'barrier_unittest.py',
    'migrate_unittest.py', 
    'frontend_unittest.py',
    ))


root = os.path.abspath(os.path.dirname(__file__))
modules = []

def lister(short, dirname, files):
    for f in files:
        if f.endswith('_unittest.py'):
            if short and f in LONG_TESTS:
                continue
            temp = os.path.join(dirname, f).strip('.py')
            mod_name = ['autotest_lib'] + temp[len(root)+1:].split('/')
            modules.append(mod_name)


def run_test(mod_name):
    mod = common.setup_modules.import_module(mod_name[-1],
                                             '.'.join(mod_name[:-1]))
    test = unittest.defaultTestLoader.loadTestsFromModule(mod)
    suite = unittest.TestSuite(test)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    return (result.errors, result.failures)


def run_tests(start, short=False):
    os.path.walk(start, lister, short)

    errors = []
    for module in modules:
        pid = os.fork()
        if pid == 0:
            errors, failures = run_test(module)
            if errors or failures:
                os._exit(1)
            os._exit(0)

        _, status = os.waitpid(pid, 0)
        if status != 0:
            errors.append('.'.join(module))
    return errors


if __name__ == "__main__":
    if len(sys.argv) == 2:
        start = os.path.join(root, sys.argv[1])
    else:
        start = root

    errors = run_tests(start)
    if errors:
        print "%d tests resulted in an error/failure:" % len(errors)
        for error in errors:
            print "\t%s" % error
        sys.exit(1)
    else:
        print "All passed!"
        sys.exit(0)
