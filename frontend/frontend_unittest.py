#!/usr/bin/python

"""
This file provides a unittest.TestCase wrapper around the Django unit test
runner.
"""
import common
import unittest
from django.core import management
from autotest_lib.frontend import settings


class FrontendTest(unittest.TestCase):
    def test_all(self):
        management.setup_environ(settings)
        from autotest_lib.frontend.afe import test
        errors = test.run_tests()
        self.assert_(errors == 0, '%s failures in frontend unit tests' % errors)

if __name__ == '__main__':
    unittest.main()
