#!/usr/bin/python

"""
This file provides a unittest.TestCase wrapper around the Django unit test
runner.
"""

import unittest, os
import common

manage_path = os.path.join(os.path.dirname(__file__), 'manage.py')

class FrontendTest(unittest.TestCase):
	def test_all(self):
		result = os.system(manage_path + ' test')
		self.assert_(result == 0)


if __name__ == '__main__':
	unittest.main()
