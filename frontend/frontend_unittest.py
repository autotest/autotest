#!/usr/bin/python

import unittest, os
import common
from autotest_lib.frontend import setup_django_environment
from autotest_lib.frontend import setup_test_environment
from autotest_lib.frontend.afe import test, readonly_connection

_APP_DIR = os.path.join(os.path.dirname(__file__), 'afe')

class FrontendTest(unittest.TestCase):
    def setUp(self):
        setup_test_environment.set_up()


    def tearDown(self):
        setup_test_environment.tear_down()


    def test_all(self):
        doctest_runner = test.DoctestRunner(_APP_DIR, 'frontend.afe')
        errors = doctest_runner.run_tests()
        self.assert_(errors == 0, '%s failures in frontend unit tests' % errors)


if __name__ == '__main__':
    unittest.main()
