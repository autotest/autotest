#!/usr/bin/python

import os, sys, unittest
import common

root = os.path.abspath(os.path.dirname(__file__))
suites = unittest.TestSuite()
def lister(dummy, dirname, files):
    for f in files:
        if f.endswith('_unittest.py'):
            temp = os.path.join(dirname, f).strip('.py')
            mod_name = ['autotest_lib'] + temp[len(root)+1:].split('/')
            mod = common.setup_modules.import_module(mod_name[-1],
                                                     '.'.join(mod_name[:-1]))
            try:
                loader = unittest.defaultTestLoader
                suite = loader.loadTestsFromModule(mod)
                suites.addTest(suite)
            except Exception, err:
                print "module %s failed to load: %s" % (mod_name, err)


if __name__ == "__main__":
    if len(sys.argv) == 2:
        start = os.path.join(root, sys.argv[1])
    else:
        start = root
    os.path.walk(start, lister, None)
    runner = unittest.TextTestRunner(verbosity=2)
    runner.run(suites)
