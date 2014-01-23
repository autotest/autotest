#!/usr/bin/python

import logging
try:
    import autotest.common as common
except ImportError:
    import common
from autotest.client.shared.test_utils import mock, unittest
from autotest.frontend import setup_django_environment
from autotest.scheduler import monitor_db
from autotest.scheduler import scheduler_config, host_scheduler
from autotest.scheduler import scheduler_models
from autotest.scheduler import test_utils


class HostSchedulerTest(test_utils.BaseSchedulerTest):

    def test_check_atomic_group_labels(self):
        # Either point to a valid meta host specification here (label) or
        # set it to None so that the job will not be assigned based on labels.
        # Previous approach (passing 0) assumed django would map it to NULL
        # at the database type/dialect handling layer.
        normal_job = self._create_job(metahosts=[1])
        atomic_job = self._create_job(atomic_group=1)
        # Indirectly initialize the internal state of the host scheduler.
        self._dispatcher._refresh_pending_queue_entries()

        atomic_hqe = scheduler_models.HostQueueEntry.fetch(where='job_id=%d' %
                                                           atomic_job.id)[0]
        normal_hqe = scheduler_models.HostQueueEntry.fetch(where='job_id=%d' %
                                                           normal_job.id)[0]

        host_scheduler = self._dispatcher._host_scheduler
        self.assertTrue(host_scheduler._check_atomic_group_labels(
            [self.label4.id], atomic_hqe))
        self.assertFalse(host_scheduler._check_atomic_group_labels(
            [self.label4.id], normal_hqe))
        self.assertFalse(host_scheduler._check_atomic_group_labels(
            [self.label5.id, self.label6.id, self.label7.id], normal_hqe))
        self.assertTrue(host_scheduler._check_atomic_group_labels(
            [self.label4.id, self.label6.id], atomic_hqe))
        self.assertTrue(host_scheduler._check_atomic_group_labels(
                        [self.label4.id, self.label5.id],
                        atomic_hqe))

    def test_get_host_atomic_group_id(self):
        job = self._create_job(metahosts=[self.label6.id])
        queue_entry = scheduler_models.HostQueueEntry.fetch(
            where='job_id=%d' % job.id)[0]
        # Indirectly initialize the internal state of the host scheduler.
        self._dispatcher._refresh_pending_queue_entries()

        # Test the host scheduler
        host_scheduler = self._dispatcher._host_scheduler

        # Two labels each in a different atomic group.  This should log an
        # error and continue.
        orig_logging_error = logging.error

        def mock_logging_error(message, *args):
            mock_logging_error._num_calls += 1
            # Test the logging call itself, we just wrapped it to count it.
            orig_logging_error(message, *args)

        mock_logging_error._num_calls = 0
        self.god.stub_with(logging, 'error', mock_logging_error)
        self.assertNotEquals(None, host_scheduler._get_host_atomic_group_id(
            [self.label4.id, self.label8.id], queue_entry))
        self.assertTrue(mock_logging_error._num_calls > 0)
        self.god.unstub(logging, 'error')

        # Two labels both in the same atomic group, this should not raise an
        # error, it will merely cause the job to schedule on the intersection.
        self.assertEquals(1, host_scheduler._get_host_atomic_group_id(
            [self.label4.id, self.label5.id]))

        self.assertEquals(None, host_scheduler._get_host_atomic_group_id([]))
        self.assertEquals(None, host_scheduler._get_host_atomic_group_id(
            [self.label3.id, self.label7.id, self.label6.id]))
        self.assertEquals(1, host_scheduler._get_host_atomic_group_id(
            [self.label4.id, self.label7.id, self.label6.id]))
        self.assertEquals(1, host_scheduler._get_host_atomic_group_id(
            [self.label7.id, self.label5.id]))


if __name__ == '__main__':
    unittest.main()
