#!/usr/bin/python

import unittest, os
from django.core import management
import common
from autotest_lib.frontend import django_test_utils

# must call setup_test_environ() before importing any Django code
django_test_utils.setup_test_environ()
from autotest_lib.frontend.afe import test, readonly_connection

_APP_DIR = os.path.join(os.path.dirname(__file__), 'afe')

class FrontendTest(unittest.TestCase):
    def setUp(self):
        readonly_connection.ReadOnlyConnection.set_testing_mode(True)


    def tearDown(self):
        readonly_connection.ReadOnlyConnection.set_testing_mode(False)


    def test_all(self):
        doctest_runner = test.DoctestRunner(_APP_DIR, 'frontend.afe')
        errors = doctest_runner.run_tests()
        self.assert_(errors == 0, '%s failures in frontend unit tests' % errors)


if __name__ == '__main__':
    unittest.main()
