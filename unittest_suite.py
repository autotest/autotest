#!/usr/bin/python

import os, sys
import unittest
import common

root = os.path.abspath(os.path.dirname(__file__))
suites = []
def lister(dummy, dirname, files):
    loader = unittest.TestLoader()
    for f in files:
        if f.endswith('_unittest.py'):
            temp = os.path.join(dirname, f).strip('.py')
            mod = 'autotest_lib' + temp[len(root):].replace('/', '.')
            try:
                suite = loader.loadTestsFromName(mod)
                suites.append(suite)
            except Exception, err:
                print "module %s failed to load: %s" % (mod, err)


if __name__ == "__main__":
    if len(sys.argv) == 2:
        start = os.path.join(root, sys.argv[1])
    else:
        start = root
    os.path.walk(start, lister, None)
    alltests = unittest.TestSuite(suites)
    runner = unittest.TextTestRunner(verbosity=2)
    runner.run(alltests)
