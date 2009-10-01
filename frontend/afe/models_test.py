#!/usr/bin/python

import unittest
import common
from autotest_lib.frontend import setup_django_environment
from autotest_lib.frontend.afe import frontend_test_utils
from autotest_lib.frontend.afe import models
from autotest_lib.frontend.afe import model_logic


class AclGroupTest(unittest.TestCase,
                   frontend_test_utils.FrontendTestMixin):
    def setUp(self):
        self._frontend_common_setup()


    def tearDown(self):
        self._frontend_common_teardown()


    def _check_acls(self, host, acl_name_list):
        actual_acl_names = [acl_group.name for acl_group
                            in host.aclgroup_set.all()]
        self.assertEquals(set(actual_acl_names), set(acl_name_list))


    def test_on_host_membership_change(self):
        host1, host2 = self.hosts[1:3]
        everyone_acl = models.AclGroup.objects.get(name='Everyone')

        host1.aclgroup_set.clear()
        self._check_acls(host1, [])
        host2.aclgroup_set.add(everyone_acl)
        self._check_acls(host2, ['Everyone', 'my_acl'])

        models.AclGroup.on_host_membership_change()

        self._check_acls(host1, ['Everyone'])
        self._check_acls(host2, ['my_acl'])


class HostTest(unittest.TestCase,
               frontend_test_utils.FrontendTestMixin):
    def setUp(self):
        self._frontend_common_setup()


    def tearDown(self):
        self._frontend_common_teardown()


    def test_add_host_previous_one_time_host(self):
        # ensure that when adding a host which was previously used as a one-time
        # host, the status isn't reset, since this can interfere with the
        # scheduler.
        host = models.Host.create_one_time_host('othost')
        self.assertEquals(host.invalid, True)
        self.assertEquals(host.status, models.Host.Status.READY)

        host.status = models.Host.Status.RUNNING
        host.save()

        host2 = models.Host.add_object(hostname='othost')
        self.assertEquals(host2.id, host.id)
        self.assertEquals(host2.status, models.Host.Status.RUNNING)


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


    def test_activate(self):
        task = self._create_task()
        task.activate()
        self.assertTrue(task.is_active)
        self.assertFalse(task.is_complete)


    def test_finish(self):
        task = self._create_task()
        task.activate()
        task.finish()
        self.assertFalse(task.is_active)
        self.assertTrue(task.is_complete)


if __name__ == '__main__':
    unittest.main()
