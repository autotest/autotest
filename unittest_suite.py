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
            mod = ('autotest_lib'
                    + temp[len(root):].replace('/', '.'))
            suite = loader.loadTestsFromName(mod)
            suites.append(suite)


if __name__ == "__main__":
    os.path.walk(root, lister, None)
    alltests = unittest.TestSuite(suites)
    runner = unittest.TextTestRunner(verbosity=2)
    runner.run(alltests)
