#!/usr/bin/python

import os, sys
import unittest

# ensure the root is where it should be
root = os.path.dirname(__file__)
sys.path.append(root)


suites = []
def lister(dummy, dirname, files):
	loader = unittest.TestLoader()
	for f in files:
		if f.endswith('_unittest.py'):
			temp = os.path.join(dirname, f).strip('.py')
			mod = temp[1:].replace('/', '.')
			suite = loader.loadTestsFromName(mod)
			suites.append(suite)


if __name__ == "__main__":
	os.path.walk(root, lister, None)
	alltests = unittest.TestSuite(suites)
	runner = unittest.TextTestRunner(verbosity=2)
	runner.run(alltests)
