#!/usr/bin/python

"""
This file provides a unittest.TestCase wrapper around the Django unit test
runner.
"""

import unittest, os
import common


class FrontendTest(unittest.TestCase):
    def test_all(self):
        manage_dir = os.path.dirname(__file__)
        result = os.system("cd %s && ./manage.py test" % (manage_dir))
        self.assert_(result == 0)


if __name__ == '__main__':
    unittest.main()
