#!/usr/bin/python

import datetime, unittest
import common
from autotest_lib.frontend import setup_django_environment
from autotest_lib.frontend.afe import frontend_test_utils
from django.db import connection
from autotest_lib.frontend.afe import models, rpc_interface, frontend_test_utils
from autotest_lib.frontend.afe import model_logic


_hqe_status = models.HostQueueEntry.Status


class RpcInterfaceTest(unittest.TestCase,
                       frontend_test_utils.FrontendTestMixin):
    def setUp(self):
        self._frontend_common_setup()


    def tearDown(self):
        self._frontend_common_teardown()


    def test_multiple_platforms(self):
        platform2 = models.Label.objects.create(name='platform2', platform=True)
        self.assertRaises(model_logic.ValidationError,
                          rpc_interface. label_add_hosts, 'platform2',
                          ['host1', 'host2'])
        self.assertRaises(model_logic.ValidationError,
                          rpc_interface.host_add_labels, 'host1', ['platform2'])
        # make sure the platform didn't get added
        platforms = rpc_interface.get_labels(
            host__hostname__in=['host1', 'host2'], platform=True)
        self.assertEquals(len(platforms), 1)
        self.assertEquals(platforms[0]['name'], 'myplatform')


    def test_get_jobs_summary(self):
        job = self._create_job(hosts=xrange(1, 4))
        entries = list(job.hostqueueentry_set.all())
        entries[1].status = _hqe_status.FAILED
        entries[1].save()
        entries[2].status = _hqe_status.FAILED
        entries[2].aborted = True
        entries[2].save()

        job_summaries = rpc_interface.get_jobs_summary(id=job.id)
        self.assertEquals(len(job_summaries), 1)
        summary = job_summaries[0]
        self.assertEquals(summary['status_counts'], {'Queued': 1,
                                                     'Failed': 2})


    def test_one_time_hosts(self):
        job = rpc_interface.create_job('test', 'Medium', 'control file',
                                       'Server', one_time_hosts=['testhost'])
        host = models.Host.objects.get(hostname='testhost')
        self.assertEquals(host.invalid, True)
        self.assertEquals(host.labels.count(), 0)
        self.assertEquals(host.aclgroup_set.count(), 0)


    def _setup_special_tasks(self):
        host = self.hosts[0]

        job1 = self._create_job(hosts=[1])
        job2 = self._create_job(hosts=[1])

        entry1 = job1.hostqueueentry_set.all()[0]
        entry1.update_object(started_on=datetime.datetime(2009, 1, 2),
                             execution_subdir='1-myuser/host1')
        entry2 = job2.hostqueueentry_set.all()[0]
        entry2.update_object(started_on=datetime.datetime(2009, 1, 3),
                             execution_subdir='2-myuser/host1')

        self.task1 = models.SpecialTask.objects.create(
                host=host, task=models.SpecialTask.Task.VERIFY,
                time_started=datetime.datetime(2009, 1, 1), # ran before job 1
                is_complete=True)
        self.task2 = models.SpecialTask.objects.create(
                host=host, task=models.SpecialTask.Task.VERIFY,
                queue_entry=entry2, # ran with job 2
                is_active=True)
        self.task3 = models.SpecialTask.objects.create(
                host=host, task=models.SpecialTask.Task.VERIFY) # not yet run


    def test_get_special_tasks(self):
        self._setup_special_tasks()
        tasks = rpc_interface.get_special_tasks(host__hostname='host1',
                                                queue_entry__isnull=True)
        self.assertEquals(len(tasks), 2)
        self.assertEquals(tasks[0]['task'], models.SpecialTask.Task.VERIFY)
        self.assertEquals(tasks[0]['is_active'], False)
        self.assertEquals(tasks[0]['is_complete'], True)


    def test_get_latest_special_task(self):
        # a particular usage of get_special_tasks()
        self._setup_special_tasks()
        self.task2.time_started = datetime.datetime(2009, 1, 2)
        self.task2.save()

        tasks = rpc_interface.get_special_tasks(
                host__hostname='host1', task=models.SpecialTask.Task.VERIFY,
                time_started__isnull=False, sort_by=['-time_started'],
                query_limit=1)
        self.assertEquals(len(tasks), 1)
        self.assertEquals(tasks[0]['id'], 2)


    def _common_entry_check(self, entry_dict):
        self.assertEquals(entry_dict['host']['hostname'], 'host1')
        self.assertEquals(entry_dict['job']['id'], 2)


    def test_get_host_queue_entries_and_special_tasks(self):
        self._setup_special_tasks()

        entries_and_tasks = (
                rpc_interface.get_host_queue_entries_and_special_tasks('host1'))

        paths = [entry['execution_path'] for entry in entries_and_tasks]
        self.assertEquals(paths, ['hosts/host1/3-verify',
                                  '2-myuser/host1',
                                  'hosts/host1/2-verify',
                                  '1-myuser/host1',
                                  'hosts/host1/1-verify'])

        verify2 = entries_and_tasks[2]
        self._common_entry_check(verify2)
        self.assertEquals(verify2['type'], 'Verify')
        self.assertEquals(verify2['status'], 'Running')
        self.assertEquals(verify2['execution_path'], 'hosts/host1/2-verify')

        entry2 = entries_and_tasks[1]
        self._common_entry_check(entry2)
        self.assertEquals(entry2['type'], 'Job')
        self.assertEquals(entry2['status'], 'Queued')
        self.assertEquals(entry2['started_on'], '2009-01-03 00:00:00')


if __name__ == '__main__':
    unittest.main()
