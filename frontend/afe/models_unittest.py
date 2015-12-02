#!/usr/bin/python

import unittest
try:
    import autotest.common as common  # pylint: disable=W0611
except ImportError:
    import common  # pylint: disable=W0611
from autotest.frontend import setup_django_environment  # pylint: disable=W0611
from autotest.frontend import test_utils
from autotest.frontend.afe import models, model_attributes
from autotest.client.shared.settings import settings

from django.db import models as dbmodels


class AclGroupTest(unittest.TestCase,
                   test_utils.FrontendTestMixin):

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
               test_utils.FrontendTestMixin):

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
                          test_utils.FrontendTestMixin):

    def setUp(self):
        self._frontend_common_setup()

    def tearDown(self):
        self._frontend_common_teardown()

    def _create_task(self):
        return models.SpecialTask.objects.create(
            host=self.hosts[0], task=models.SpecialTask.Task.VERIFY,
            requested_by=models.User.current_user())

    def test_execution_path(self):
        task = self._create_task()
        self.assertEquals(task.execution_path(), 'hosts/host1/1-verify')

    def test_status(self):
        task = self._create_task()
        self.assertEquals(task.status, 'Queued')

        task.update_object(is_active=True)
        self.assertEquals(task.status, 'Running')

        task.update_object(is_active=False, is_complete=True, success=True)
        self.assertEquals(task.status, 'Completed')

        task.update_object(success=False)
        self.assertEquals(task.status, 'Failed')

    def test_activate(self):
        task = self._create_task()
        task.activate()
        self.assertTrue(task.is_active)
        self.assertFalse(task.is_complete)

    def test_finish(self):
        task = self._create_task()
        task.activate()
        task.finish(True)
        self.assertFalse(task.is_active)
        self.assertTrue(task.is_complete)
        self.assertTrue(task.success)

    def test_requested_by_from_queue_entry(self):
        job = self._create_job(hosts=[0])
        task = models.SpecialTask.objects.create(
            host=self.hosts[0], task=models.SpecialTask.Task.VERIFY,
            queue_entry=job.hostqueueentry_set.all()[0])
        self.assertEquals(task.requested_by.login, 'autotest_system')


class HostQueueEntryUnittest(unittest.TestCase,
                             test_utils.FrontendTestMixin):

    def setUp(self):
        self._frontend_common_setup()

    def tearDown(self):
        self._frontend_common_teardown()

    def test_execution_path(self):
        entry = self._create_job(hosts=[1]).hostqueueentry_set.all()[0]
        entry.execution_subdir = 'subdir'
        entry.save()

        self.assertEquals(entry.execution_path(), '1-autotest_system/subdir')


class ModelWithInvalidTest(unittest.TestCase,
                           test_utils.FrontendTestMixin):

    def setUp(self):
        self._frontend_common_setup()

    def tearDown(self):
        self._frontend_common_teardown()

    def test_model_with_invalid_delete(self):
        self.assertFalse(self.hosts[0].invalid)
        self.hosts[0].delete()
        self.assertTrue(self.hosts[0].invalid)
        self.assertTrue(models.Host.objects.get(id=self.hosts[0].id))

    def test_model_with_invalid_delete_queryset(self):
        for host in self.hosts:
            self.assertFalse(host.invalid)

        hosts = models.Host.objects.all()
        hosts.delete()
        self.assertEqual(hosts.count(), len(self.hosts))

        for host in hosts:
            self.assertTrue(host.invalid)

    def test_cloned_queryset_delete(self):
        """
        Make sure that a cloned queryset maintains the custom delete()
        """
        to_delete = ('host1', 'host2')

        for host in self.hosts:
            self.assertFalse(host.invalid)

        hosts = models.Host.objects.all().filter(hostname__in=to_delete)
        hosts.delete()
        all_hosts = models.Host.objects.all()
        self.assertEqual(all_hosts.count(), len(self.hosts))

        for host in all_hosts:
            if host.hostname in to_delete:
                self.assertTrue(
                    host.invalid,
                    '%s.invalid expected to be True' % host.hostname)
            else:
                self.assertFalse(
                    host.invalid,
                    '%s.invalid expected to be False' % host.hostname)

    def test_normal_delete(self):
        job = self._create_job(hosts=[1])
        self.assertEqual(1, models.Job.objects.all().count())

        job.delete()
        self.assertEqual(0, models.Job.objects.all().count())

    def test_normal_delete_queryset(self):
        self._create_job(hosts=[1])
        self._create_job(hosts=[2])

        self.assertEqual(2, models.Job.objects.all().count())

        models.Job.objects.all().delete()
        self.assertEqual(0, models.Job.objects.all().count())


class KernelTest(unittest.TestCase, test_utils.FrontendTestMixin):

    def setUp(self):
        self._frontend_common_setup()

    def tearDown(self):
        self._frontend_common_teardown()

    def test_create_kernels_none(self):
        self.assertEqual(None, models.Kernel.create_kernels(None))

    def test_create_kernels(self):
        self.god.stub_function(models.Kernel, '_create')

        num_kernels = 3
        kernel_list = [object() for _ in range(num_kernels)]
        result = [object() for _ in range(num_kernels)]

        for kernel, response in zip(kernel_list, result):
            models.Kernel._create.expect_call(kernel).and_return(response)
        self.assertEqual(result, models.Kernel.create_kernels(kernel_list))
        self.god.check_playback()

    def test_create(self):
        kernel = models.Kernel._create({'version': 'version'})
        self.assertEqual(kernel.version, 'version')
        self.assertEqual(kernel.cmdline, '')
        self.assertEqual(kernel, models.Kernel._create({'version': 'version'}))


class ParameterizedJobTest(unittest.TestCase,
                           test_utils.FrontendTestMixin):

    def setUp(self):
        self._frontend_common_setup()

    def tearDown(self):
        self._frontend_common_teardown()

    def test_job(self):
        settings.override_value('AUTOTEST_WEB', 'parameterized_jobs', 'True')

        test = models.Test.objects.create(
            name='name', author='author', test_class='class',
            test_category='category',
            test_type=model_attributes.TestTypes.SERVER, path='path')
        parameterized_job = models.ParameterizedJob.objects.create(test=test)
        job = self._create_job(hosts=[1], control_file=None,
                               parameterized_job=parameterized_job)

        self.assertEqual(job, parameterized_job.job())


class JobTest(unittest.TestCase, test_utils.FrontendTestMixin):

    def setUp(self):
        self._frontend_common_setup()

    def tearDown(self):
        self._frontend_common_teardown()

    def test_check_parameterized_jobs_no_args(self):
        self.assertRaises(Exception, models.Job.check_parameterized_job,
                          control_file=None, parameterized_job=None)

    def test_check_parameterized_jobs_both_args(self):
        self.assertRaises(Exception, models.Job.check_parameterized_job,
                          control_file=object(), parameterized_job=object())

    def test_check_parameterized_jobs_disabled(self):
        self.assertRaises(Exception, models.Job.check_parameterized_job,
                          control_file=None, parameterized_job=object())

    def test_check_parameterized_jobs_enabled(self):
        settings.override_value('AUTOTEST_WEB', 'parameterized_jobs', 'True')
        self.assertRaises(Exception, models.Job.check_parameterized_job,
                          control_file=object(), parameterized_job=None)


class SoftwareComponentKindTest(unittest.TestCase,
                                test_utils.FrontendTestMixin):

    def setUp(self):
        self._frontend_common_setup()

    def tearDown(self):
        self._frontend_common_teardown()

    def test_create_delete(self):
        models.SoftwareComponentKind.objects.create(name='rpm')
        self.assertEqual(2, models.SoftwareComponentKind.objects.all().count())

        models.SoftwareComponentKind.objects.all().delete()
        self.assertEqual(0, models.SoftwareComponentKind.objects.all().count())

    def test_create_duplicate_distro(self):
        def create_kind():
            models.SoftwareComponentKind.objects.create(name='rpm')

        create_kind()
        self.assertRaises(Exception, create_kind)
        models.SoftwareComponentKind.objects.all().delete()


class SoftwareComponentArchTest(unittest.TestCase,
                                test_utils.FrontendTestMixin):

    def setUp(self):
        self._frontend_common_setup()

    def tearDown(self):
        self._frontend_common_teardown()

    def test_create_delete(self):
        models.SoftwareComponentArch.objects.create(name='x86_64')
        self.assertEqual(2, models.SoftwareComponentArch.objects.all().count())

        models.SoftwareComponentArch.objects.all().delete()
        self.assertEqual(0, models.SoftwareComponentArch.objects.all().count())

    def test_create_duplicate_distro(self):
        def create_arch():
            models.SoftwareComponentArch.objects.create(name='x86_64')

        create_arch()
        self.assertRaises(Exception, create_arch)
        models.SoftwareComponentArch.objects.all().delete()


class SoftwareComponentTest(unittest.TestCase,
                            test_utils.FrontendTestMixin):

    def setUp(self):
        self._frontend_common_setup()

    def tearDown(self):
        self._frontend_common_teardown()

    def test_delete_reference(self):
        '''
        Should not be possible to delete a Software Component Arch that
        is referenced by an existing Software Component
        '''
        kind = models.SoftwareComponentKind.objects.create(name='rpm')
        kind.save()
        kind_id = kind.id

        arch = models.SoftwareComponentArch.objects.create(name='x86_64')
        arch.save()
        arch_id = arch.id

        sc = models.SoftwareComponent.objects.create(name='foo',
                                                     kind=kind,
                                                     arch=arch,
                                                     version='1.0.0')
        sc.save()
        sc_id = sc.id
        sc = models.SoftwareComponent.objects.get(pk=sc_id)

        arch = models.SoftwareComponentArch.objects.get(pk=arch_id)

        def arch_delete():
            arch.delete()

        self.assertRaises(dbmodels.ProtectedError, arch_delete)
        models.SoftwareComponent.objects.all().delete()
        models.SoftwareComponentKind.objects.all().delete()
        models.SoftwareComponentArch.objects.all().delete()


class LinuxDistroTest(unittest.TestCase,
                      test_utils.FrontendTestMixin):

    def setUp(self):
        self._frontend_common_setup()

    def tearDown(self):
        self._frontend_common_teardown()

    def test_create_delete(self):
        # The builtin 'unknown distro' accounts for the first count
        self.assertEqual(1, models.LinuxDistro.objects.all().count())

        models.LinuxDistro.objects.create(name='distro', version='1',
                                          release='0', arch='i386')

        self.assertEqual(2, models.LinuxDistro.objects.all().count())

        models.LinuxDistro.objects.all().delete()
        self.assertEqual(0, models.LinuxDistro.objects.all().count())

    def test_create_query_arch_delete(self):
        models.LinuxDistro.objects.create(name='distro', version='1',
                                          release='0', arch='i386')
        models.LinuxDistro.objects.create(name='distro', version='1',
                                          release='1', arch='i386')
        models.LinuxDistro.objects.create(name='distro', version='1',
                                          release='0', arch='x86_64')
        models.LinuxDistro.objects.create(name='distro', version='1',
                                          release='1', arch='x86_64')

        all_count = models.LinuxDistro.objects.all().count()
        self.assertEqual(all_count, 5)
        i386_count = models.LinuxDistro.query_objects({'arch': 'i386'}).count()
        self.assertEqual(i386_count, 2)

        models.LinuxDistro.objects.get(name='distro', version='1',
                                       release='0', arch='i386').delete()
        models.LinuxDistro.objects.get(name='distro', version='1',
                                       release='1', arch='i386').delete()
        self.assertEqual(3, models.LinuxDistro.objects.all().count())

    def test_create_duplicate_distro(self):
        def create_distro():
            models.LinuxDistro.objects.create(name='distro', version='1',
                                              release='0', arch='i386')

        create_distro()
        self.assertRaises(Exception, create_distro)
        models.LinuxDistro.objects.all().delete()


if __name__ == '__main__':
    unittest.main()
