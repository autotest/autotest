#!/usr/bin/python2.4

"""
This file provides a unittest.TestCase wrapper around the Django unit test
runner.
"""

import unittest, os

manage_path = os.path.join(os.path.dirname(__file__), 'manage.py')

class FrontendTest(unittest.TestCase):
	def test_all(self):
		result = os.system(manage_path + ' test')
		self.assert_(result == 0)


if __name__ == '__main__':
	unittest.main()
