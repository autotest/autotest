#!/usr/bin/python

import unittest
import common
from autotest_lib.frontend import setup_django_environment
from autotest_lib.frontend.afe import frontend_test_utils
from autotest_lib.frontend.afe import models

class SpecialTaskUnittest(unittest.TestCase,
                          frontend_test_utils.FrontendTestMixin):
    def setUp(self):
        self._frontend_common_setup()


    def tearDown(self):
        self._frontend_common_teardown()


    def _create_task(self):
        return models.SpecialTask.objects.create(
                host=self.hosts[0], task=models.SpecialTask.Task.VERIFY)


    def test_execution_path(self):
        task = self._create_task()
        self.assertEquals(task.execution_path(), 'hosts/host1/1-verify')


    def test_status(self):
        task = self._create_task()
        self.assertEquals(task.status, 'Queued')

        task.update_object(is_active=True)
        self.assertEquals(task.status, 'Running')

        task.update_object(is_active=False, is_complete=True)
        self.assertEquals(task.status, 'Completed')


if __name__ == '__main__':
    unittest.main()
