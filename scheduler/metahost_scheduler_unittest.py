#!/usr/bin/python

try:
    import autotest.common as common  # pylint: disable=W0611
except ImportError:
    import common  # pylint: disable=W0611
import unittest
from autotest.client.shared.test_utils import mock
from autotest.frontend import setup_django_environment  # pylint: disable=W0611
from autotest.frontend import setup_test_environment  # pylint: disable=W0611
from autotest.scheduler import metahost_scheduler, scheduler_models


class LabelMetahostSchedulerTest(unittest.TestCase):

    def setUp(self):
        self.god = mock.mock_god()
        self.scheduling_utility = self.god.create_mock_class(
            metahost_scheduler.HostSchedulingUtility, 'utility')
        self.metahost_scheduler = metahost_scheduler.LabelMetahostScheduler()

    def tearDown(self):
        self.god.unstub_all()

    def entry(self):
        return self.god.create_mock_class(scheduler_models.HostQueueEntry,
                                          'entry')

    def test_can_schedule_metahost(self):
        entry = self.entry()
        entry.meta_host = None
        self.assertFalse(self.metahost_scheduler.can_schedule_metahost(entry))

        entry.meta_host = 1
        self.assert_(self.metahost_scheduler.can_schedule_metahost(entry))

    def test_schedule_metahost(self):
        entry = self.entry()
        entry.meta_host = 1
        host = object()

        self.scheduling_utility.hosts_in_label.expect_call(1).and_return(
            [2, 3, 4, 5])
        # 2 is in ineligible_hosts
        (self.scheduling_utility.ineligible_hosts_for_entry.expect_call(entry)
         .and_return([2]))
        self.scheduling_utility.is_host_usable.expect_call(2).and_return(True)
        # 3 is unusable
        self.scheduling_utility.is_host_usable.expect_call(3).and_return(False)
        self.scheduling_utility.remove_host_from_label.expect_call(3, 1)
        # 4 is ineligible for the job
        self.scheduling_utility.is_host_usable.expect_call(4).and_return(True)
        (self.scheduling_utility.is_host_eligible_for_job.expect_call(4, entry)
         .and_return(False))
        # 5 runs
        self.scheduling_utility.is_host_usable.expect_call(5).and_return(True)
        (self.scheduling_utility.is_host_eligible_for_job.expect_call(5, entry)
         .and_return(True))
        self.scheduling_utility.remove_host_from_label.expect_call(5, 1)
        self.scheduling_utility.pop_host.expect_call(5).and_return(host)
        entry.set_host.expect_call(host)

        self.metahost_scheduler.schedule_metahost(entry,
                                                  self.scheduling_utility)
        self.god.check_playback()

    def test_no_hosts(self):
        entry = self.entry()
        entry.meta_host = 1

        self.scheduling_utility.hosts_in_label.expect_call(1).and_return(())
        (self.scheduling_utility.ineligible_hosts_for_entry.expect_call(entry)
         .and_return(()))

        self.metahost_scheduler.schedule_metahost(entry,
                                                  self.scheduling_utility)
        self.god.check_playback()


if __name__ == '__main__':
    unittest.main()
