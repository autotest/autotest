#!/usr/bin/python

import os
import unittest

try:
    import autotest.common as common  # pylint: disable=W0611
except ImportError:
    import common  # pylint: disable=W0611
from autotest.frontend import setup_django_environment  # pylint: disable=W0611
from autotest.frontend import setup_test_environment  # pylint: disable=W0611
from autotest.frontend.afe import test
from autotest.client.shared import settings

_APP_DIR = os.path.join(os.path.dirname(__file__), 'afe')


class FrontendTest(unittest.TestCase):

    def setUp(self):
        setup_test_environment.set_up()
        settings.settings.override_value('AUTOTEST_WEB', 'parameterized_jobs',
                                         'False')
        settings.settings.override_value('SERVER', 'rpc_logging', 'False')

    def tearDown(self):
        setup_test_environment.tear_down()

    def test_all(self):
        doctest_runner = test.DoctestRunner(_APP_DIR, 'autotest.frontend.afe')
        errors = doctest_runner.run_tests()
        self.assert_(errors == 0, '%s failures in frontend unit tests' % errors)


if __name__ == '__main__':
    unittest.main()
