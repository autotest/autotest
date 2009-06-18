#!/usr/bin/python2.4

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
        job = self._create_job(xrange(3))
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


if __name__ == '__main__':
    unittest.main()
