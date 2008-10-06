#!/usr/bin/python

"""
This file provides a unittest.TestCase wrapper around the Django unit test
runner.
"""
import unittest
from django.core import management
import common

def setup_test_environ():
    from autotest_lib.frontend import settings
    management.setup_environ(settings)
    from django.conf import settings
    # django.conf.settings.LazySettings is buggy and requires us to get
    # something from it before we set stuff on it
    getattr(settings, 'DATABASE_ENGINE')
    settings.DATABASE_ENGINE = 'sqlite3'
    settings.DATABASE_NAME = ':memory:'

# must call setup_test_environ() before importing any Django code
setup_test_environ()
from autotest_lib.frontend.afe import test, readonly_connection

class FrontendTest(unittest.TestCase):
    def setUp(self):
        readonly_connection.ReadOnlyConnection.set_testing_mode(True)


    def tearDown(self):
        readonly_connection.ReadOnlyConnection.set_testing_mode(False)


    def test_all(self):
        errors = test.run_tests()
        self.assert_(errors == 0, '%s failures in frontend unit tests' % errors)

if __name__ == '__main__':
    unittest.main()
