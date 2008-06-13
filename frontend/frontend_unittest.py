#!/usr/bin/python

"""
This file provides a unittest.TestCase wrapper around the Django unit test
runner.
"""

import unittest
from django.core import management
import settings


class FrontendTest(unittest.TestCase):
    def test_all(self):
        management.setup_environ(settings)
        from frontend.afe import test
        errors = test.run_tests()
        self.assert_(errors == 0, '%s failures in frontend unit tests' % errors)

if __name__ == '__main__':
    unittest.main()
