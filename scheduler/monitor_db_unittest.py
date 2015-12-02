#!/usr/bin/python

import gc
import logging
import time
import unittest
try:
    import autotest.common as common  # pylint: disable=W0611
except ImportError:
    import common  # pylint: disable=W0611
from autotest.frontend import setup_django_environment  # pylint: disable=W0611
from autotest.frontend import test_utils
from autotest.client.shared import mail
from autotest.client.shared.test_utils import mock
from autotest.database_legacy import database_connection
from autotest.frontend.afe import models
from autotest.scheduler import monitor_db, drone_manager
from autotest.scheduler import scheduler_config, gc_stats, host_scheduler
from autotest.scheduler import monitor_db_functional_unittest
from autotest.scheduler import scheduler_models

_DEBUG = False


class DummyAgentTask(object):
    num_processes = 1
    owner_username = 'my_user'

    def get_drone_hostnames_allowed(self):
        return None


class DummyAgent(object):
    started = False
    _is_done = False
    host_ids = ()
    queue_entry_ids = ()

    def __init__(self):
        self.task = DummyAgentTask()

    def tick(self):
        self.started = True

    def is_done(self):
        return self._is_done

    def set_done(self, done):
        self._is_done = done


class IsRow(mock.argument_comparator):

    def __init__(self, row_id):
        self.row_id = row_id

    def is_satisfied_by(self, parameter):
        return list(parameter)[0] == self.row_id

    def __str__(self):
        return 'row with id %s' % self.row_id


class IsAgentWithTask(mock.argument_comparator):

    def __init__(self, task):
        self._task = task

    def is_satisfied_by(self, parameter):
        if not isinstance(parameter, monitor_db.Agent):
            return False
        tasks = list(parameter.queue.queue)
        if len(tasks) != 1:
            return False
        return tasks[0] == self._task


def _set_host_and_qe_ids(agent_or_task, id_list=None):
    if id_list is None:
        id_list = []
    agent_or_task.host_ids = agent_or_task.queue_entry_ids = id_list


class BaseSchedulerTest(unittest.TestCase,
                        test_utils.FrontendTestMixin):
    _config_section = 'AUTOTEST_WEB'

    def _do_query(self, sql):
        self._database.execute(sql)

    def _set_monitor_stubs(self):
        # Clear the instance cache as this is a brand new database.
        scheduler_models.DBObject._clear_instance_cache()

        self._database = (
            database_connection.TranslatingDatabase.get_test_database(
                translators=monitor_db_functional_unittest._DB_TRANSLATORS))
        self._database.connect(db_type='django')
        self._database.debug = _DEBUG

        self.god.stub_with(monitor_db, '_db', self._database)
        self.god.stub_with(scheduler_models, '_db', self._database)
        self.god.stub_with(drone_manager.instance(), '_results_dir',
                           '/test/path')
        self.god.stub_with(drone_manager.instance(), '_temporary_directory',
                           '/test/path/tmp')

        monitor_db.initialize_globals()
        scheduler_models.initialize_globals()

    def setUp(self):
        self._frontend_common_setup()
        self._set_monitor_stubs()
        self._dispatcher = monitor_db.Dispatcher()

    def tearDown(self):
        self._database.disconnect()
        self._frontend_common_teardown()

    def _update_hqe(self, set, where=''):
        query = 'UPDATE afe_host_queue_entries SET ' + set
        if where:
            query += ' WHERE ' + where
        self._do_query(query)


class DispatcherSchedulingTest(BaseSchedulerTest):
    _jobs_scheduled = []

    def tearDown(self):
        super(DispatcherSchedulingTest, self).tearDown()

    def _set_monitor_stubs(self):
        super(DispatcherSchedulingTest, self)._set_monitor_stubs()

        def hqe__do_schedule_pre_job_tasks_stub(queue_entry):
            """Called by HostQueueEntry.run()."""
            self._record_job_scheduled(queue_entry.job.id, queue_entry.host.id)
            queue_entry.set_status('Starting')

        self.god.stub_with(scheduler_models.HostQueueEntry,
                           '_do_schedule_pre_job_tasks',
                           hqe__do_schedule_pre_job_tasks_stub)

        def hqe_queue_log_record_stub(self, log_line):
            """No-Op to avoid calls down to the _drone_manager during tests."""

        self.god.stub_with(scheduler_models.HostQueueEntry, 'queue_log_record',
                           hqe_queue_log_record_stub)

    def _record_job_scheduled(self, job_id, host_id):
        record = (job_id, host_id)
        self.assert_(record not in self._jobs_scheduled,
                     'Job %d scheduled on host %d twice' %
                     (job_id, host_id))
        self._jobs_scheduled.append(record)

    def _assert_job_scheduled_on(self, job_id, host_id):
        record = (job_id, host_id)
        self.assert_(record in self._jobs_scheduled,
                     'Job %d not scheduled on host %d as expected\n'
                     'Jobs scheduled: %s' %
                     (job_id, host_id, self._jobs_scheduled))
        self._jobs_scheduled.remove(record)

    def _assert_job_scheduled_on_number_of(self, job_id, host_ids, number):
        """Assert job was scheduled on exactly number hosts out of a set."""
        found = []
        for host_id in host_ids:
            record = (job_id, host_id)
            if record in self._jobs_scheduled:
                found.append(record)
                self._jobs_scheduled.remove(record)
        if len(found) < number:
            self.fail('Job %d scheduled on fewer than %d hosts in %s.\n'
                      'Jobs scheduled: %s' % (job_id, number, host_ids, found))
        elif len(found) > number:
            self.fail('Job %d scheduled on more than %d hosts in %s.\n'
                      'Jobs scheduled: %s' % (job_id, number, host_ids, found))

    def _check_for_extra_schedulings(self):
        if len(self._jobs_scheduled) != 0:
            self.fail('Extra jobs scheduled: ' +
                      str(self._jobs_scheduled))

    def _convert_jobs_to_metahosts(self, *job_ids):
        sql_tuple = '(' + ','.join(str(i) for i in job_ids) + ')'
        self._do_query('UPDATE afe_host_queue_entries SET '
                       'meta_host=host_id, host_id=NULL '
                       'WHERE job_id IN ' + sql_tuple)

    def _lock_host(self, host_id):
        self._do_query('UPDATE afe_hosts SET locked=1 WHERE id=' +
                       str(host_id))

    def setUp(self):
        super(DispatcherSchedulingTest, self).setUp()
        self._jobs_scheduled = []

    def _run_scheduler(self):
        for _ in xrange(2):  # metahost scheduling can take two cycles
            self._dispatcher._schedule_new_jobs()

    def _test_basic_scheduling_helper(self, use_metahosts):
        'Basic nonmetahost scheduling'
        self._create_job_simple([1], use_metahosts)
        self._create_job_simple([2], use_metahosts)
        self._run_scheduler()
        self._assert_job_scheduled_on(1, 1)
        self._assert_job_scheduled_on(2, 2)
        self._check_for_extra_schedulings()

    def _test_priorities_helper(self, use_metahosts):
        'Test prioritization ordering'
        self._create_job_simple([1], use_metahosts)
        self._create_job_simple([2], use_metahosts)
        self._create_job_simple([1, 2], use_metahosts)
        self._create_job_simple([1], use_metahosts, priority=1)
        self._run_scheduler()
        self._assert_job_scheduled_on(4, 1)  # higher priority
        self._assert_job_scheduled_on(2, 2)  # earlier job over later
        self._check_for_extra_schedulings()

    def _test_hosts_ready_helper(self, use_metahosts):
        """
        Only hosts that are status=Ready, unlocked and not invalid get
        scheduled.
        """
        self._create_job_simple([1], use_metahosts)
        self._do_query('UPDATE afe_hosts SET status="Running" WHERE id=1')
        self._run_scheduler()
        self._check_for_extra_schedulings()

        self._do_query('UPDATE afe_hosts SET status="Ready", locked=1 '
                       'WHERE id=1')
        self._run_scheduler()
        self._check_for_extra_schedulings()

        self._do_query('UPDATE afe_hosts SET locked=0, invalid=1 '
                       'WHERE id=1')
        self._run_scheduler()
        if not use_metahosts:
            self._assert_job_scheduled_on(1, 1)
        self._check_for_extra_schedulings()

    def _test_hosts_idle_helper(self, use_metahosts):
        'Only idle hosts get scheduled'
        self._create_job(hosts=[1], active=True)
        self._create_job_simple([1], use_metahosts)
        self._run_scheduler()
        self._check_for_extra_schedulings()

    def _test_obey_ACLs_helper(self, use_metahosts):
        self._do_query('DELETE FROM afe_acl_groups_hosts WHERE host_id=1')
        self._create_job_simple([1], use_metahosts)
        self._run_scheduler()
        self._check_for_extra_schedulings()

    def test_basic_scheduling(self):
        self._test_basic_scheduling_helper(False)

    def test_priorities(self):
        self._test_priorities_helper(False)

    def test_hosts_ready(self):
        self._test_hosts_ready_helper(False)

    def test_hosts_idle(self):
        self._test_hosts_idle_helper(False)

    def test_obey_ACLs(self):
        self._test_obey_ACLs_helper(False)

    def test_one_time_hosts_ignore_ACLs(self):
        self._do_query('DELETE FROM afe_acl_groups_hosts WHERE host_id=1')
        self._do_query('UPDATE afe_hosts SET invalid=1 WHERE id=1')
        self._create_job_simple([1])
        self._run_scheduler()
        self._assert_job_scheduled_on(1, 1)
        self._check_for_extra_schedulings()

    def test_non_metahost_on_invalid_host(self):
        """
        Non-metahost entries can get scheduled on invalid hosts (this is how
        one-time hosts work).
        """
        self._do_query('UPDATE afe_hosts SET invalid=1')
        self._test_basic_scheduling_helper(False)

    def test_metahost_scheduling(self):
        """
        Basic metahost scheduling
        """
        self._test_basic_scheduling_helper(True)

    def test_metahost_priorities(self):
        self._test_priorities_helper(True)

    def test_metahost_hosts_ready(self):
        self._test_hosts_ready_helper(True)

    def test_metahost_hosts_idle(self):
        self._test_hosts_idle_helper(True)

    def test_metahost_obey_ACLs(self):
        self._test_obey_ACLs_helper(True)

    def _setup_test_only_if_needed_labels(self):
        # apply only_if_needed label3 to host1
        models.Host.smart_get('host1').labels.add(self.label3)
        return self._create_job_simple([1], use_metahost=True)

    def test_only_if_needed_labels_avoids_host(self):
        job = self._setup_test_only_if_needed_labels()
        # if the job doesn't depend on label3, there should be no scheduling
        self._run_scheduler()
        self._check_for_extra_schedulings()

    def test_only_if_needed_labels_schedules(self):
        job = self._setup_test_only_if_needed_labels()
        job.dependency_labels.add(self.label3)
        self._run_scheduler()
        self._assert_job_scheduled_on(1, 1)
        self._check_for_extra_schedulings()

    def test_only_if_needed_labels_via_metahost(self):
        job = self._setup_test_only_if_needed_labels()
        job.dependency_labels.add(self.label3)
        # should also work if the metahost is the only_if_needed label
        self._do_query('DELETE FROM afe_jobs_dependency_labels')
        self._create_job(metahosts=[3])
        self._run_scheduler()
        self._assert_job_scheduled_on(2, 1)
        self._check_for_extra_schedulings()

    def test_nonmetahost_over_metahost(self):
        """
        Non-metahost entries should take priority over metahost entries
        for the same host
        """
        self._create_job(metahosts=[1])
        self._create_job(hosts=[1])
        self._run_scheduler()
        self._assert_job_scheduled_on(2, 1)
        self._check_for_extra_schedulings()

    def test_metahosts_obey_blocks(self):
        """
        Metahosts can't get scheduled on hosts already scheduled for
        that job.
        """
        self._create_job(metahosts=[1], hosts=[1])
        # make the nonmetahost entry complete, so the metahost can try
        # to get scheduled
        self._update_hqe(set='complete = 1', where='host_id=1')
        self._run_scheduler()
        self._check_for_extra_schedulings()

    # TODO(gps): These should probably live in their own TestCase class
    # specific to testing HostScheduler methods directly.  It was convenient
    # to put it here for now to share existing test environment setup code.
    def test_HostScheduler_check_atomic_group_labels(self):
        normal_job = self._create_job(metahosts=[0])
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

    def test_HostScheduler_get_host_atomic_group_id(self):
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

    def test_atomic_group_hosts_blocked_from_non_atomic_jobs(self):
        # Create a job scheduled to run on label6.
        self._create_job(metahosts=[self.label6.id])
        self._run_scheduler()
        # label6 only has hosts that are in atomic groups associated with it,
        # there should be no scheduling.
        self._check_for_extra_schedulings()

    def test_atomic_group_hosts_blocked_from_non_atomic_jobs_explicit(self):
        # Create a job scheduled to run on label5.  This is an atomic group
        # label but this job does not request atomic group scheduling.
        self._create_job(metahosts=[self.label5.id])
        self._run_scheduler()
        # label6 only has hosts that are in atomic groups associated with it,
        # there should be no scheduling.
        self._check_for_extra_schedulings()

    def test_atomic_group_scheduling_basics(self):
        # Create jobs scheduled to run on an atomic group.
        job_a = self._create_job(synchronous=True, metahosts=[self.label4.id],
                                 atomic_group=1)
        job_b = self._create_job(synchronous=True, metahosts=[self.label5.id],
                                 atomic_group=1)
        self._run_scheduler()
        # atomic_group.max_number_of_machines was 2 so we should run on 2.
        self._assert_job_scheduled_on_number_of(job_a.id, (5, 6, 7), 2)
        self._assert_job_scheduled_on(job_b.id, 8)  # label5
        self._assert_job_scheduled_on(job_b.id, 9)  # label5
        self._check_for_extra_schedulings()

        # The three host label4 atomic group still has one host available.
        # That means a job with a synch_count of 1 asking to be scheduled on
        # the atomic group can still use the final machine.
        #
        # This may seem like a somewhat odd use case.  It allows the use of an
        # atomic group as a set of machines to run smaller jobs within (a set
        # of hosts configured for use in network tests with eachother perhaps?)
        onehost_job = self._create_job(atomic_group=1)
        self._run_scheduler()
        self._assert_job_scheduled_on_number_of(onehost_job.id, (5, 6, 7), 1)
        self._check_for_extra_schedulings()

        # No more atomic groups have hosts available, no more jobs should
        # be scheduled.
        self._create_job(atomic_group=1)
        self._run_scheduler()
        self._check_for_extra_schedulings()

    def test_atomic_group_scheduling_obeys_acls(self):
        # Request scheduling on a specific atomic label but be denied by ACLs.
        self._do_query('DELETE FROM afe_acl_groups_hosts '
                       'WHERE host_id in (8,9)')
        job = self._create_job(metahosts=[self.label5.id], atomic_group=1)
        self._run_scheduler()
        self._check_for_extra_schedulings()

    def test_atomic_group_scheduling_dependency_label_exclude(self):
        # A dependency label that matches no hosts in the atomic group.
        job_a = self._create_job(atomic_group=1)
        job_a.dependency_labels.add(self.label3)
        self._run_scheduler()
        self._check_for_extra_schedulings()

    def test_atomic_group_scheduling_metahost_dependency_label_exclude(self):
        # A metahost and dependency label that excludes too many hosts.
        job_b = self._create_job(synchronous=True, metahosts=[self.label4.id],
                                 atomic_group=1)
        job_b.dependency_labels.add(self.label7)
        self._run_scheduler()
        self._check_for_extra_schedulings()

    def test_atomic_group_scheduling_dependency_label_match(self):
        # A dependency label that exists on enough atomic group hosts in only
        # one of the two atomic group labels.
        job_c = self._create_job(synchronous=True, atomic_group=1)
        job_c.dependency_labels.add(self.label7)
        self._run_scheduler()
        self._assert_job_scheduled_on_number_of(job_c.id, (8, 9), 2)
        self._check_for_extra_schedulings()

    def test_atomic_group_scheduling_no_metahost(self):
        # Force it to schedule on the other group for a reliable test.
        self._do_query('UPDATE afe_hosts SET invalid=1 WHERE id=9')
        # An atomic job without a metahost.
        job = self._create_job(synchronous=True, atomic_group=1)
        self._run_scheduler()
        self._assert_job_scheduled_on_number_of(job.id, (5, 6, 7), 2)
        self._check_for_extra_schedulings()

    def test_atomic_group_scheduling_partial_group(self):
        # Make one host in labels[3] unavailable so that there are only two
        # hosts left in the group.
        self._do_query('UPDATE afe_hosts SET status="Repair Failed" WHERE id=5')
        job = self._create_job(synchronous=True, metahosts=[self.label4.id],
                               atomic_group=1)
        self._run_scheduler()
        # Verify that it was scheduled on the 2 ready hosts in that group.
        self._assert_job_scheduled_on(job.id, 6)
        self._assert_job_scheduled_on(job.id, 7)
        self._check_for_extra_schedulings()

    def test_atomic_group_scheduling_not_enough_available(self):
        # Mark some hosts in each atomic group label as not usable.
        # One host running, another invalid in the first group label.
        self._do_query('UPDATE afe_hosts SET status="Running" WHERE id=5')
        self._do_query('UPDATE afe_hosts SET invalid=1 WHERE id=6')
        # One host invalid in the second group label.
        self._do_query('UPDATE afe_hosts SET invalid=1 WHERE id=9')
        # Nothing to schedule when no group label has enough (2) good hosts..
        self._create_job(atomic_group=1, synchronous=True)
        self._run_scheduler()
        # There are not enough hosts in either atomic group,
        # No more scheduling should occur.
        self._check_for_extra_schedulings()

        # Now create an atomic job that has a synch count of 1.  It should
        # schedule on exactly one of the hosts.
        onehost_job = self._create_job(atomic_group=1)
        self._run_scheduler()
        self._assert_job_scheduled_on_number_of(onehost_job.id, (7, 8), 1)

    def test_atomic_group_scheduling_no_valid_hosts(self):
        self._do_query('UPDATE afe_hosts SET invalid=1 WHERE id in (8,9)')
        self._create_job(synchronous=True, metahosts=[self.label5.id],
                         atomic_group=1)
        self._run_scheduler()
        # no hosts in the selected group and label are valid.  no schedulings.
        self._check_for_extra_schedulings()

    def test_atomic_group_scheduling_metahost_works(self):
        # Test that atomic group scheduling also obeys metahosts.
        self._create_job(metahosts=[0], atomic_group=1)
        self._run_scheduler()
        # There are no atomic group hosts that also have that metahost.
        self._check_for_extra_schedulings()

        job_b = self._create_job(metahosts=[self.label5.id], atomic_group=1)
        self._run_scheduler()
        self._assert_job_scheduled_on(job_b.id, 8)
        self._assert_job_scheduled_on(job_b.id, 9)
        self._check_for_extra_schedulings()

    def test_atomic_group_skips_ineligible_hosts(self):
        # Test hosts marked ineligible for this job are not eligible.
        # How would this ever happen anyways?
        job = self._create_job(metahosts=[self.label4.id], atomic_group=1)
        models.IneligibleHostQueue.objects.create(job=job, host_id=5)
        models.IneligibleHostQueue.objects.create(job=job, host_id=6)
        models.IneligibleHostQueue.objects.create(job=job, host_id=7)
        self._run_scheduler()
        # No scheduling should occur as all desired hosts were ineligible.
        self._check_for_extra_schedulings()

    def test_atomic_group_scheduling_fail(self):
        # If synch_count is > the atomic group number of machines, the job
        # should be aborted immediately.
        model_job = self._create_job(synchronous=True, atomic_group=1)
        model_job.synch_count = 4
        model_job.save()
        job = scheduler_models.Job(id=model_job.id)
        self._run_scheduler()
        self._check_for_extra_schedulings()
        queue_entries = job.get_host_queue_entries()
        self.assertEqual(1, len(queue_entries))
        self.assertEqual(queue_entries[0].status,
                         models.HostQueueEntry.Status.ABORTED)

    def test_atomic_group_no_labels_no_scheduling(self):
        # Never schedule on atomic groups marked invalid.
        job = self._create_job(metahosts=[self.label5.id], synchronous=True,
                               atomic_group=1)
        # Deleting an atomic group via the frontend marks it invalid and
        # removes all label references to the group.  The job now references
        # an invalid atomic group with no labels associated with it.
        self.label5.atomic_group.invalid = True
        self.label5.atomic_group.save()
        self.label5.atomic_group = None
        self.label5.save()

        self._run_scheduler()
        self._check_for_extra_schedulings()

    def test_schedule_directly_on_atomic_group_host_fail(self):
        # Scheduling a job directly on hosts in an atomic group must
        # fail to avoid users inadvertently holding up the use of an
        # entire atomic group by using the machines individually.
        job = self._create_job(hosts=[5])
        self._run_scheduler()
        self._check_for_extra_schedulings()

    def test_schedule_directly_on_atomic_group_host(self):
        # Scheduling a job directly on one host in an atomic group will
        # work when the atomic group is listed on the HQE in addition
        # to the host (assuming the sync count is 1).
        job = self._create_job(hosts=[5], atomic_group=1)
        self._run_scheduler()
        self._assert_job_scheduled_on(job.id, 5)
        self._check_for_extra_schedulings()

    def test_schedule_directly_on_atomic_group_hosts_sync2(self):
        job = self._create_job(hosts=[5, 8], atomic_group=1, synchronous=True)
        self._run_scheduler()
        self._assert_job_scheduled_on(job.id, 5)
        self._assert_job_scheduled_on(job.id, 8)
        self._check_for_extra_schedulings()

    def test_schedule_directly_on_atomic_group_hosts_wrong_group(self):
        job = self._create_job(hosts=[5, 8], atomic_group=2, synchronous=True)
        self._run_scheduler()
        self._check_for_extra_schedulings()

    def test_only_schedule_queued_entries(self):
        self._create_job(metahosts=[1])
        self._update_hqe(set='active=1, host_id=2')
        self._run_scheduler()
        self._check_for_extra_schedulings()

    def test_no_ready_hosts(self):
        self._create_job(hosts=[1])
        self._do_query('UPDATE afe_hosts SET status="Repair Failed"')
        self._run_scheduler()
        self._check_for_extra_schedulings()

    def test_garbage_collection(self):
        self.god.stub_with(self._dispatcher, '_seconds_between_garbage_stats',
                           999999)
        self.god.stub_function(gc, 'collect')
        self.god.stub_function(gc_stats, '_log_garbage_collector_stats')
        gc.collect.expect_call().and_return(0)
        gc_stats._log_garbage_collector_stats.expect_call()
        # Force a garbage collection run
        self._dispatcher._last_garbage_stats_time = 0
        self._dispatcher._garbage_collection()
        # The previous call should have reset the time, it won't do anything
        # the second time.  If it does, we'll get an unexpected call.
        self._dispatcher._garbage_collection()


class DispatcherThrottlingTest(BaseSchedulerTest):

    """
    Test that the dispatcher throttles:
     * total number of running processes
     * number of processes started per cycle
    """
    _MAX_RUNNING = 3
    _MAX_STARTED = 2

    def setUp(self):
        super(DispatcherThrottlingTest, self).setUp()
        scheduler_config.config.max_processes_per_drone = self._MAX_RUNNING
        scheduler_config.config.max_processes_started_per_cycle = (
            self._MAX_STARTED)

        def fake_max_runnable_processes(fake_self, username,
                                        drone_hostnames_allowed):
            running = sum(agent.task.num_processes
                          for agent in self._agents
                          if agent.started and not agent.is_done())
            return self._MAX_RUNNING - running
        self.god.stub_with(drone_manager.DroneManager, 'max_runnable_processes',
                           fake_max_runnable_processes)

    def _setup_some_agents(self, num_agents):
        self._agents = [DummyAgent() for i in xrange(num_agents)]
        self._dispatcher._agents = list(self._agents)

    def _run_a_few_cycles(self):
        for i in xrange(4):
            self._dispatcher._handle_agents()

    def _assert_agents_started(self, indexes, is_started=True):
        for i in indexes:
            self.assert_(self._agents[i].started == is_started,
                         'Agent %d %sstarted' %
                         (i, is_started and 'not ' or ''))

    def _assert_agents_not_started(self, indexes):
        self._assert_agents_started(indexes, False)

    def test_throttle_total(self):
        self._setup_some_agents(4)
        self._run_a_few_cycles()
        self._assert_agents_started([0, 1, 2])
        self._assert_agents_not_started([3])

    def test_throttle_per_cycle(self):
        self._setup_some_agents(3)
        self._dispatcher._handle_agents()
        self._assert_agents_started([0, 1])
        self._assert_agents_not_started([2])

    def test_throttle_with_synchronous(self):
        self._setup_some_agents(2)
        self._agents[0].task.num_processes = 3
        self._run_a_few_cycles()
        self._assert_agents_started([0])
        self._assert_agents_not_started([1])

    def test_large_agent_starvation(self):
        """
        Ensure large agents don't get starved by lower-priority agents.
        """
        self._setup_some_agents(3)
        self._agents[1].task.num_processes = 3
        self._run_a_few_cycles()
        self._assert_agents_started([0])
        self._assert_agents_not_started([1, 2])

        self._agents[0].set_done(True)
        self._run_a_few_cycles()
        self._assert_agents_started([1])
        self._assert_agents_not_started([2])

    def test_zero_process_agent(self):
        self._setup_some_agents(5)
        self._agents[4].task.num_processes = 0
        self._run_a_few_cycles()
        self._assert_agents_started([0, 1, 2, 4])
        self._assert_agents_not_started([3])


class PidfileRunMonitorTest(unittest.TestCase):
    execution_tag = 'test_tag'
    pid = 12345
    process = drone_manager.Process('myhost', pid)
    num_tests_failed = 1

    def setUp(self):
        self.god = mock.mock_god()
        self.mock_drone_manager = self.god.create_mock_class(
            drone_manager.DroneManager, 'drone_manager')
        self.god.stub_with(monitor_db, '_drone_manager',
                           self.mock_drone_manager)
        self.god.stub_function(mail.manager, 'enqueue_admin')
        self.god.stub_with(monitor_db, '_get_pidfile_timeout_secs',
                           self._mock_get_pidfile_timeout_secs)

        self.pidfile_id = object()

        (self.mock_drone_manager.get_pidfile_id_from
             .expect_call(self.execution_tag,
                          pidfile_name=drone_manager.AUTOSERV_PID_FILE)
             .and_return(self.pidfile_id))

        self.monitor = monitor_db.PidfileRunMonitor()
        self.monitor.attach_to_existing_process(self.execution_tag)

    def tearDown(self):
        self.god.unstub_all()

    def _mock_get_pidfile_timeout_secs(self):
        return 300

    def setup_pidfile(self, pid=None, exit_code=None, tests_failed=None,
                      use_second_read=False):
        contents = drone_manager.PidfileContents()
        if pid is not None:
            contents.process = drone_manager.Process('myhost', pid)
        contents.exit_status = exit_code
        contents.num_tests_failed = tests_failed
        self.mock_drone_manager.get_pidfile_contents.expect_call(
            self.pidfile_id, use_second_read=use_second_read).and_return(
            contents)

    def set_not_yet_run(self):
        self.setup_pidfile()

    def set_empty_pidfile(self):
        self.setup_pidfile()

    def set_running(self, use_second_read=False):
        self.setup_pidfile(self.pid, use_second_read=use_second_read)

    def set_complete(self, error_code, use_second_read=False):
        self.setup_pidfile(self.pid, error_code, self.num_tests_failed,
                           use_second_read=use_second_read)

    def _check_monitor(self, expected_pid, expected_exit_status,
                       expected_num_tests_failed):
        if expected_pid is None:
            self.assertEquals(self.monitor._state.process, None)
        else:
            self.assertEquals(self.monitor._state.process.pid, expected_pid)
        self.assertEquals(self.monitor._state.exit_status, expected_exit_status)
        self.assertEquals(self.monitor._state.num_tests_failed,
                          expected_num_tests_failed)

        self.god.check_playback()

    def _test_read_pidfile_helper(self, expected_pid, expected_exit_status,
                                  expected_num_tests_failed):
        self.monitor._read_pidfile()
        self._check_monitor(expected_pid, expected_exit_status,
                            expected_num_tests_failed)

    def _get_expected_tests_failed(self, expected_exit_status):
        if expected_exit_status is None:
            expected_tests_failed = None
        else:
            expected_tests_failed = self.num_tests_failed
        return expected_tests_failed

    def test_read_pidfile(self):
        self.set_not_yet_run()
        self._test_read_pidfile_helper(None, None, None)

        self.set_empty_pidfile()
        self._test_read_pidfile_helper(None, None, None)

        self.set_running()
        self._test_read_pidfile_helper(self.pid, None, None)

        self.set_complete(123)
        self._test_read_pidfile_helper(self.pid, 123, self.num_tests_failed)

    def test_read_pidfile_error(self):
        self.mock_drone_manager.get_pidfile_contents.expect_call(
            self.pidfile_id, use_second_read=False).and_return(
            drone_manager.InvalidPidfile('error'))
        self.assertRaises(monitor_db.PidfileRunMonitor._PidfileException,
                          self.monitor._read_pidfile)
        self.god.check_playback()

    def setup_is_running(self, is_running):
        self.mock_drone_manager.is_process_running.expect_call(
            self.process).and_return(is_running)

    def _test_get_pidfile_info_helper(self, expected_pid, expected_exit_status,
                                      expected_num_tests_failed):
        self.monitor._get_pidfile_info()
        self._check_monitor(expected_pid, expected_exit_status,
                            expected_num_tests_failed)

    def test_get_pidfile_info(self):
        """
        normal cases for get_pidfile_info
        """
        # running
        self.set_running()
        self.setup_is_running(True)
        self._test_get_pidfile_info_helper(self.pid, None, None)

        # exited during check
        self.set_running()
        self.setup_is_running(False)
        self.set_complete(123, use_second_read=True)  # pidfile gets read again
        self._test_get_pidfile_info_helper(self.pid, 123, self.num_tests_failed)

        # completed
        self.set_complete(123)
        self._test_get_pidfile_info_helper(self.pid, 123, self.num_tests_failed)

    def test_get_pidfile_info_running_no_proc(self):
        """
        pidfile shows process running, but no proc exists
        """
        # running but no proc
        self.set_running()
        self.setup_is_running(False)
        self.set_running(use_second_read=True)
        mail.manager.enqueue_admin.expect_call(mock.is_string_comparator(),
                                               mock.is_string_comparator())
        self._test_get_pidfile_info_helper(self.pid, 1, 0)
        self.assertTrue(self.monitor.lost_process)

    def test_get_pidfile_info_not_yet_run(self):
        """
        pidfile hasn't been written yet
        """
        self.set_not_yet_run()
        self._test_get_pidfile_info_helper(None, None, None)

    def test_process_failed_to_write_pidfile(self):
        self.set_not_yet_run()
        mail.manager.enqueue_admin.expect_call(mock.is_string_comparator(),
                                               mock.is_string_comparator())
        self.monitor._start_time = (time.time() -
                                    monitor_db._get_pidfile_timeout_secs() - 1)
        self._test_get_pidfile_info_helper(None, 1, 0)
        self.assertTrue(self.monitor.lost_process)


class AgentTest(unittest.TestCase):

    def setUp(self):
        self.god = mock.mock_god()
        self._dispatcher = self.god.create_mock_class(monitor_db.Dispatcher,
                                                      'dispatcher')

    def tearDown(self):
        self.god.unstub_all()

    def _create_mock_task(self, name):
        task = self.god.create_mock_class(monitor_db.AgentTask, name)
        task.num_processes = 1
        _set_host_and_qe_ids(task)
        return task

    def _create_agent(self, task):
        agent = monitor_db.Agent(task)
        agent.dispatcher = self._dispatcher
        return agent

    def _finish_agent(self, agent):
        while not agent.is_done():
            agent.tick()

    def test_agent_abort(self):
        task = self._create_mock_task('task')
        task.poll.expect_call()
        task.is_done.expect_call().and_return(False)
        task.abort.expect_call()
        task.aborted = True

        agent = self._create_agent(task)
        agent.tick()
        agent.abort()
        self._finish_agent(agent)
        self.god.check_playback()

    def _test_agent_abort_before_started_helper(self, ignore_abort=False):
        task = self._create_mock_task('task')
        task.abort.expect_call()
        if ignore_abort:
            task.aborted = False
            task.poll.expect_call()
            task.is_done.expect_call().and_return(True)
            task.success = True
        else:
            task.aborted = True

        agent = self._create_agent(task)
        agent.abort()
        self._finish_agent(agent)
        self.god.check_playback()

    def test_agent_abort_before_started(self):
        self._test_agent_abort_before_started_helper()
        self._test_agent_abort_before_started_helper(True)


class JobSchedulingTest(BaseSchedulerTest):

    def _test_run_helper(self, expect_agent=True, expect_starting=False,
                         expect_pending=False):
        if expect_starting:
            expected_status = models.HostQueueEntry.Status.STARTING
        elif expect_pending:
            expected_status = models.HostQueueEntry.Status.PENDING
        else:
            expected_status = models.HostQueueEntry.Status.VERIFYING
        job = scheduler_models.Job.fetch('id = 1')[0]
        queue_entry = scheduler_models.HostQueueEntry.fetch('id = 1')[0]
        assert queue_entry.job is job
        job.run_if_ready(queue_entry)

        self.god.check_playback()

        self._dispatcher._schedule_delay_tasks()
        self._dispatcher._schedule_running_host_queue_entries()
        agent = self._dispatcher._agents[0]

        actual_status = models.HostQueueEntry.smart_get(1).status
        self.assertEquals(expected_status, actual_status)

        if not expect_agent:
            self.assertEquals(agent, None)
            return

        self.assert_(isinstance(agent, monitor_db.Agent))
        self.assert_(agent.task)
        return agent.task

    def test_run_if_ready_delays(self):
        # Also tests Job.run_with_ready_delay() on atomic group jobs.
        django_job = self._create_job(hosts=[5, 6], atomic_group=1)
        job = scheduler_models.Job(django_job.id)
        self.assertEqual(1, job.synch_count)
        django_hqes = list(models.HostQueueEntry.objects.filter(job=job.id))
        self.assertEqual(2, len(django_hqes))
        self.assertEqual(2, django_hqes[0].atomic_group.max_number_of_machines)

        def set_hqe_status(django_hqe, status):
            django_hqe.status = status
            django_hqe.save()
            scheduler_models.HostQueueEntry(django_hqe.id).host.set_status(status)

        # An initial state, our synch_count is 1
        set_hqe_status(django_hqes[0], models.HostQueueEntry.Status.VERIFYING)
        set_hqe_status(django_hqes[1], models.HostQueueEntry.Status.PENDING)

        # So that we don't depend on the config file value during the test.
        self.assert_(scheduler_config.config
                     .secs_to_wait_for_atomic_group_hosts is not None)
        self.god.stub_with(scheduler_config.config,
                           'secs_to_wait_for_atomic_group_hosts', 123456)

        # Get the pending one as a scheduler_models.HostQueueEntry object.
        hqe = scheduler_models.HostQueueEntry(django_hqes[1].id)
        self.assert_(not job._delay_ready_task)
        self.assertTrue(job.is_ready())

        # Ready with one pending, one verifying and an atomic group should
        # result in a DelayCallTask to re-check if we're ready a while later.
        job.run_if_ready(hqe)
        self.assertEquals('Waiting', hqe.status)
        self._dispatcher._schedule_delay_tasks()
        self.assertEquals('Pending', hqe.status)
        agent = self._dispatcher._agents[0]
        self.assert_(job._delay_ready_task)
        self.assert_(isinstance(agent, monitor_db.Agent))
        self.assert_(agent.task)
        delay_task = agent.task
        self.assert_(isinstance(delay_task, scheduler_models.DelayedCallTask))
        self.assert_(not delay_task.is_done())

        self.god.stub_function(delay_task, 'abort')

        self.god.stub_function(job, 'run')

        self.god.stub_function(job, '_pending_count')
        self.god.stub_with(job, 'synch_count', 9)
        self.god.stub_function(job, 'request_abort')

        # Test that the DelayedCallTask's callback queued up above does the
        # correct thing and does not call run if there are not enough hosts
        # in pending after the delay.
        job._pending_count.expect_call().and_return(0)
        job.request_abort.expect_call()
        delay_task._callback()
        self.god.check_playback()

        # Test that the DelayedCallTask's callback queued up above does the
        # correct thing and returns the Agent returned by job.run() if
        # there are still enough hosts pending after the delay.
        job.synch_count = 4
        job._pending_count.expect_call().and_return(4)
        job.run.expect_call(hqe)
        delay_task._callback()
        self.god.check_playback()

        job._pending_count.expect_call().and_return(4)

        # Adjust the delay deadline so that enough time has passed.
        job._delay_ready_task.end_time = time.time() - 111111
        job.run.expect_call(hqe)
        # ...the delay_expired condition should cause us to call run()
        self._dispatcher._handle_agents()
        self.god.check_playback()
        delay_task.success = False

        # Adjust the delay deadline back so that enough time has not passed.
        job._delay_ready_task.end_time = time.time() + 111111
        self._dispatcher._handle_agents()
        self.god.check_playback()

        # Now max_number_of_machines HQEs are in pending state.  Remaining
        # delay will now be ignored.
        other_hqe = scheduler_models.HostQueueEntry(django_hqes[0].id)
        self.god.unstub(job, 'run')
        self.god.unstub(job, '_pending_count')
        self.god.unstub(job, 'synch_count')
        self.god.unstub(job, 'request_abort')
        # ...the over_max_threshold test should cause us to call run()
        delay_task.abort.expect_call()
        other_hqe.on_pending()
        self.assertEquals('Starting', other_hqe.status)
        self.assertEquals('Starting', hqe.status)
        self.god.stub_function(job, 'run')
        self.god.unstub(delay_task, 'abort')

        hqe.set_status('Pending')
        other_hqe.set_status('Pending')
        # Now we're not over the max for the atomic group.  But all assigned
        # hosts are in pending state.  over_max_threshold should make us run().
        hqe.atomic_group.max_number_of_machines += 1
        hqe.atomic_group.save()
        job.run.expect_call(hqe)
        hqe.on_pending()
        self.god.check_playback()
        hqe.atomic_group.max_number_of_machines -= 1
        hqe.atomic_group.save()

        other_hqe = scheduler_models.HostQueueEntry(django_hqes[0].id)
        self.assertTrue(hqe.job is other_hqe.job)
        # DBObject classes should reuse instances so these should be the same.
        self.assertEqual(job, other_hqe.job)
        self.assertEqual(other_hqe.job, hqe.job)
        # Be sure our delay was not lost during the other_hqe construction.
        self.assertEqual(job._delay_ready_task, delay_task)
        self.assert_(job._delay_ready_task)
        self.assertFalse(job._delay_ready_task.is_done())
        self.assertFalse(job._delay_ready_task.aborted)

        # We want the real run() to be called below.
        self.god.unstub(job, 'run')

        # We pass in the other HQE this time the same way it would happen
        # for real when one host finishes verifying and enters pending.
        job.run_if_ready(other_hqe)

        # The delayed task must be aborted by the actual run() call above.
        self.assertTrue(job._delay_ready_task.aborted)
        self.assertFalse(job._delay_ready_task.success)
        self.assertTrue(job._delay_ready_task.is_done())

        # Check that job run() and _finish_run() were called by the above:
        self._dispatcher._schedule_running_host_queue_entries()
        agent = self._dispatcher._agents[0]
        self.assert_(agent.task)
        task = agent.task
        self.assert_(isinstance(task, monitor_db.QueueTask))
        # Requery these hqes in order to verify the status from the DB.
        django_hqes = list(models.HostQueueEntry.objects.filter(job=job.id))
        for entry in django_hqes:
            self.assertEqual(models.HostQueueEntry.Status.STARTING,
                             entry.status)

        # We're already running, but more calls to run_with_ready_delay can
        # continue to come in due to straggler hosts enter Pending.  Make
        # sure we don't do anything.
        self.god.stub_function(job, 'run')
        job.run_with_ready_delay(hqe)
        self.god.check_playback()
        self.god.unstub(job, 'run')

    def test_run_synchronous_atomic_group_ready(self):
        self._create_job(hosts=[5, 6], atomic_group=1, synchronous=True)
        self._update_hqe("status='Pending', execution_subdir=''")

        queue_task = self._test_run_helper(expect_starting=True)

        self.assert_(isinstance(queue_task, monitor_db.QueueTask))
        # Atomic group jobs that do not depend on a specific label in the
        # atomic group will use the atomic group name as their group name.
        self.assertEquals(queue_task.queue_entries[0].get_group_name(),
                          'atomic1')

    def test_run_synchronous_atomic_group_with_label_ready(self):
        job = self._create_job(hosts=[5, 6], atomic_group=1, synchronous=True)
        job.dependency_labels.add(self.label4)
        self._update_hqe("status='Pending', execution_subdir=''")

        queue_task = self._test_run_helper(expect_starting=True)

        self.assert_(isinstance(queue_task, monitor_db.QueueTask))
        # Atomic group jobs that also specify a label in the atomic group
        # will use the label name as their group name.
        self.assertEquals(queue_task.queue_entries[0].get_group_name(),
                          'label4')

    def test_run_synchronous_ready(self):
        self._create_job(hosts=[1, 2], synchronous=True)
        self._update_hqe("status='Pending', execution_subdir=''")

        queue_task = self._test_run_helper(expect_starting=True)

        self.assert_(isinstance(queue_task, monitor_db.QueueTask))
        self.assertEquals(queue_task.job.id, 1)
        hqe_ids = [hqe.id for hqe in queue_task.queue_entries]
        self.assertEquals(hqe_ids, [1, 2])

    def test_schedule_running_host_queue_entries_fail(self):
        self._create_job(hosts=[2])
        self._update_hqe("status='%s', execution_subdir=''" %
                         models.HostQueueEntry.Status.PENDING)
        job = scheduler_models.Job.fetch('id = 1')[0]
        queue_entry = scheduler_models.HostQueueEntry.fetch('id = 1')[0]
        assert queue_entry.job is job
        job.run_if_ready(queue_entry)
        self.assertEqual(queue_entry.status,
                         models.HostQueueEntry.Status.STARTING)
        self.assert_(queue_entry.execution_subdir)
        self.god.check_playback()

        class dummy_test_agent(object):
            task = 'dummy_test_agent'
        self._dispatcher._register_agent_for_ids(
            self._dispatcher._host_agents, [queue_entry.host.id],
            dummy_test_agent)

        # Attempted to schedule on a host that already has an agent.
        self.assertRaises(host_scheduler.SchedulerError,
                          self._dispatcher._schedule_running_host_queue_entries)

    def test_schedule_hostless_job(self):
        job = self._create_job(hostless=True)
        self.assertEqual(1, job.hostqueueentry_set.count())
        hqe_query = scheduler_models.HostQueueEntry.fetch(
            'id = %s' % job.hostqueueentry_set.all()[0].id)
        self.assertEqual(1, len(hqe_query))
        hqe = hqe_query[0]

        self.assertEqual(models.HostQueueEntry.Status.QUEUED, hqe.status)
        self.assertEqual(0, len(self._dispatcher._agents))

        self._dispatcher._schedule_new_jobs()

        self.assertEqual(models.HostQueueEntry.Status.STARTING, hqe.status)
        self.assertEqual(1, len(self._dispatcher._agents))

        self._dispatcher._schedule_new_jobs()

        # No change to previously schedule hostless job, and no additional agent
        self.assertEqual(models.HostQueueEntry.Status.STARTING, hqe.status)
        self.assertEqual(1, len(self._dispatcher._agents))


class TopLevelFunctionsTest(unittest.TestCase):

    def setUp(self):
        self.god = mock.mock_god()

    def tearDown(self):
        self.god.unstub_all()

    def test_autoserv_command_line(self):
        machines_s = 'abcd12,efgh34'
        machines = ('abcd12', 'efgh34')
        profiles = ('fedora17', 'fedora18')
        machines_profiles = 'abcd12#fedora17,efgh34#fedora18'
        extra_args = ['-Z', 'hello']

        # ecl is our expected command line
        # cl is our actual command line
        ecl_base = set((monitor_db._autoserv_path, '-p', '-m', machines_s, '-r',
                        drone_manager.WORKING_DIRECTORY))
        ecl_profiles = set((monitor_db._autoserv_path, '-p', '-m',
                            machines_profiles, '-r',
                            drone_manager.WORKING_DIRECTORY))
        ecl = ecl_base.union(['--verbose']).union(extra_args)
        ecl_profiles = ecl_profiles.union(['--verbose']).union(extra_args)
        cl = set(monitor_db._autoserv_command_line(machines, [], extra_args))
        cl_profiles = set(
            monitor_db._autoserv_command_line(machines, profiles, extra_args))

        self.assertEqual(ecl, cl)
        self.assertEqual(ecl_profiles, cl_profiles)

        class FakeJob(object):
            owner = 'Bob'
            name = 'fake job name'

        class FakeHQE(object):
            job = FakeJob

        ecl = ecl_base.union(['-u', FakeJob.owner, '-l', FakeJob.name])
        ecl_profiles = ecl_profiles.union(['-u', FakeJob.owner, '-l',
                                           FakeJob.name])
        cl = set(monitor_db._autoserv_command_line(machines, profiles=[],
                                                   extra_args=[], job=FakeJob,
                                                   queue_entry=FakeHQE,
                                                   verbose=False))
        cl_profiles = set(monitor_db._autoserv_command_line(machines,
                                                            profiles=profiles,
                                                            extra_args=extra_args,
                                                            job=FakeJob,
                                                            queue_entry=FakeHQE,
                                                            verbose=True))

        self.assertEqual(ecl, cl)
        self.assertEqual(ecl_profiles, cl_profiles)


class AgentTaskTest(unittest.TestCase,
                    test_utils.FrontendTestMixin):

    def setUp(self):
        self._frontend_common_setup()

    def tearDown(self):
        self._frontend_common_teardown()

    def _setup_drones(self):
        self.god.stub_function(models.DroneSet, 'drone_sets_enabled')
        models.DroneSet.drone_sets_enabled.expect_call().and_return(True)

        drones = []
        for x in xrange(4):
            drones.append(models.Drone.objects.create(hostname=str(x)))

        drone_set_1 = models.DroneSet.objects.create(name='1')
        drone_set_1.drones.add(*drones[0:2])
        drone_set_2 = models.DroneSet.objects.create(name='2')
        drone_set_2.drones.add(*drones[2:4])
        drone_set_3 = models.DroneSet.objects.create(name='3')

        job_1 = self._create_job_simple([self.hosts[0].id],
                                        drone_set=drone_set_1)
        job_2 = self._create_job_simple([self.hosts[0].id],
                                        drone_set=drone_set_2)
        job_3 = self._create_job_simple([self.hosts[0].id],
                                        drone_set=drone_set_3)

        job_4 = self._create_job_simple([self.hosts[0].id])
        job_4.drone_set = None
        job_4.save()

        hqe_1 = job_1.hostqueueentry_set.all()[0]
        hqe_2 = job_2.hostqueueentry_set.all()[0]
        hqe_3 = job_3.hostqueueentry_set.all()[0]
        hqe_4 = job_4.hostqueueentry_set.all()[0]

        return (hqe_1, hqe_2, hqe_3, hqe_4), monitor_db.AgentTask()

    def test_get_drone_hostnames_allowed_no_drones_in_set(self):
        hqes, task = self._setup_drones()
        task.queue_entry_ids = (hqes[2].id,)
        self.assertEqual(set(), task.get_drone_hostnames_allowed())
        self.god.check_playback()

    def test_get_drone_hostnames_allowed_no_drone_set(self):
        hqes, task = self._setup_drones()
        hqe = hqes[3]
        task.queue_entry_ids = (hqe.id,)

        result = object()

        self.god.stub_function(task, '_user_or_global_default_drone_set')
        task._user_or_global_default_drone_set.expect_call(
            hqe.job, hqe.job.user()).and_return(result)

        self.assertEqual(result, task.get_drone_hostnames_allowed())
        self.god.check_playback()

    def test_get_drone_hostnames_allowed_success(self):
        hqes, task = self._setup_drones()
        task.queue_entry_ids = (hqes[0].id,)
        self.assertEqual(set(('0', '1')), task.get_drone_hostnames_allowed())
        self.god.check_playback()

    def test_get_drone_hostnames_allowed_multiple_jobs(self):
        hqes, task = self._setup_drones()
        task.queue_entry_ids = (hqes[0].id, hqes[1].id)
        self.assertRaises(AssertionError,
                          task.get_drone_hostnames_allowed)
        self.god.check_playback()

    def test_get_drone_hostnames_allowed_no_hqe(self):
        class MockSpecialTask(object):
            requested_by = object()

        class MockSpecialAgentTask(monitor_db.SpecialAgentTask):
            task = MockSpecialTask()
            queue_entry_ids = []

            def __init__(self, *args, **kwargs):
                pass

        task = MockSpecialAgentTask()
        self.god.stub_function(models.DroneSet, 'drone_sets_enabled')
        self.god.stub_function(task, '_user_or_global_default_drone_set')

        result = object()
        models.DroneSet.drone_sets_enabled.expect_call().and_return(True)
        task._user_or_global_default_drone_set.expect_call(
            task.task, MockSpecialTask.requested_by).and_return(result)

        self.assertEqual(result, task.get_drone_hostnames_allowed())
        self.god.check_playback()

    def _setup_test_user_or_global_default_drone_set(self):
        result = object()

        class MockDroneSet(object):

            def get_drone_hostnames(self):
                return result

        self.god.stub_function(models.DroneSet, 'get_default')
        models.DroneSet.get_default.expect_call().and_return(MockDroneSet())
        return result

    def test_user_or_global_default_drone_set(self):
        expected = object()

        class MockDroneSet(object):

            def get_drone_hostnames(self):
                return expected

        class MockUser(object):
            drone_set = MockDroneSet()

        self._setup_test_user_or_global_default_drone_set()

        actual = monitor_db.AgentTask()._user_or_global_default_drone_set(
            None, MockUser())

        self.assertEqual(expected, actual)
        self.god.check_playback()

    def test_user_or_global_default_drone_set_no_user(self):
        expected = self._setup_test_user_or_global_default_drone_set()
        actual = monitor_db.AgentTask()._user_or_global_default_drone_set(
            None, None)

        self.assertEqual(expected, actual)
        self.god.check_playback()

    def test_user_or_global_default_drone_set_no_user_drone_set(self):
        class MockUser(object):
            drone_set = None
            login = None

        expected = self._setup_test_user_or_global_default_drone_set()
        actual = monitor_db.AgentTask()._user_or_global_default_drone_set(
            None, MockUser())

        self.assertEqual(expected, actual)
        self.god.check_playback()


if __name__ == '__main__':
    unittest.main()
