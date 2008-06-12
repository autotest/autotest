#!/usr/bin/python

import os, sys
import unittest

# ensure the root is where it should be
root = os.path.abspath(os.path.dirname(__file__))
from client import setup_modules
setup_modules.setup(base_path=root, root_module_name="autotest_lib")


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
                print "module failed to load: %s: %s" % (mod, err)


if __name__ == "__main__":
    if len(sys.argv) == 2:
        start = os.path.join(root, sys.argv[1])
    else:
        start = root
    os.path.walk(start, lister, None)
    alltests = unittest.TestSuite(suites)
    runner = unittest.TextTestRunner(verbosity=2)
    runner.run(alltests)
