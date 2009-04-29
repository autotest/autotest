#!/usr/bin/python

import unittest, time, subprocess, os, StringIO, tempfile, datetime, shutil
import common
import MySQLdb
from autotest_lib.frontend import setup_django_environment
from autotest_lib.frontend import setup_test_environment
from autotest_lib.client.common_lib import global_config, host_protections
from autotest_lib.client.common_lib.test_utils import mock
from autotest_lib.database import database_connection, migrate
from autotest_lib.frontend import thread_local
from autotest_lib.frontend.afe import models
from autotest_lib.scheduler import monitor_db, drone_manager, email_manager
from autotest_lib.scheduler import scheduler_config

_DEBUG = False


class DummyAgent(object):
    _is_running = False
    _is_done = False
    num_processes = 1
    host_ids = []
    queue_entry_ids = []

    def is_running(self):
        return self._is_running


    def tick(self):
        self._is_running = True


    def is_done(self):
        return self._is_done


    def set_done(self, done):
        self._is_done = done
        self._is_running = not done


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


class BaseSchedulerTest(unittest.TestCase):
    _config_section = 'AUTOTEST_WEB'
    _test_db_initialized = False

    def _do_query(self, sql):
        self._database.execute(sql)


    @classmethod
    def _initialize_test_db(cls):
        if cls._test_db_initialized:
            return
        temp_fd, cls._test_db_file = tempfile.mkstemp(suffix='.monitor_test')
        os.close(temp_fd)
        setup_test_environment.set_test_database(cls._test_db_file)
        setup_test_environment.run_syncdb()
        cls._test_db_backup = setup_test_environment.backup_test_database()
        cls._test_db_initialized = True


    def _open_test_db(self):
        self._initialize_test_db()
        setup_test_environment.restore_test_database(self._test_db_backup)
        self._database = (
            database_connection.DatabaseConnection.get_test_database(
                self._test_db_file))
        self._database.connect()
        self._database.debug = _DEBUG


    def _close_test_db(self):
        self._database.disconnect()


    def _set_monitor_stubs(self):
        # Clear the instance cache as this is a brand new database.
        monitor_db.DBObject._clear_instance_cache()
        monitor_db._db = self._database
        monitor_db._drone_manager._results_dir = '/test/path'
        monitor_db._drone_manager._temporary_directory = '/test/path/tmp'


    def _fill_in_test_data(self):
        """Populate the test database with some hosts and labels."""
        user = models.User.objects.create(login='my_user')
        acl_group = models.AclGroup.objects.create(name='my_acl')
        acl_group.users.add(user)

        hosts = [models.Host.objects.create(hostname=hostname) for hostname in
                 ('host1', 'host2', 'host3', 'host4', 'host5', 'host6',
                  'host7', 'host8', 'host9')]

        acl_group.hosts = hosts
        models.AclGroup.smart_get('Everyone').hosts = []

        labels = [models.Label.objects.create(name=name) for name in
                  ('label1', 'label2', 'label3', 'label4', 'label5', 'label6',
                   'label7')]

        atomic_group1 = models.AtomicGroup.objects.create(
                name='atomic1', max_number_of_machines=2)
        atomic_group2 = models.AtomicGroup.objects.create(
                name='atomic2', max_number_of_machines=2)

        self.label3 = labels[2]
        self.label3.only_if_needed = True
        self.label3.save()
        self.label4 = labels[3]
        self.label4.atomic_group = atomic_group1
        self.label4.save()
        self.label5 = labels[4]
        self.label5.atomic_group = atomic_group1
        self.label5.save()
        hosts[0].labels.add(labels[0])  # label1
        hosts[1].labels.add(labels[1])  # label2
        self.label6 = labels[5]
        self.label7 = labels[6]
        for hostnum in xrange(4,7):  # host5..host7
            hosts[hostnum].labels.add(self.label4)  # an atomic group lavel
            hosts[hostnum].labels.add(self.label6)  # a normal label
        hosts[6].labels.add(self.label7)
        for hostnum in xrange(7,9):  # host8..host9
            hosts[hostnum].labels.add(self.label5)  # an atomic group lavel
            hosts[hostnum].labels.add(self.label6)  # a normal label
            hosts[hostnum].labels.add(self.label7)


    def _setup_dummy_user(self):
        user = models.User.objects.create(login='dummy', access_level=100)
        thread_local.set_user(user)


    def setUp(self):
        self.god = mock.mock_god()
        self._open_test_db()
        self._fill_in_test_data()
        self._set_monitor_stubs()
        self._dispatcher = monitor_db.Dispatcher()
        self._setup_dummy_user()


    def tearDown(self):
        self._close_test_db()
        self.god.unstub_all()


    def _create_job(self, hosts=[], metahosts=[], priority=0, active=False,
                    synchronous=False, atomic_group=None):
        """
        Create a job row in the test database.

        @param hosts - A list of explicit host ids for this job to be
                scheduled on.
        @param metahosts - A list of label ids for each host that this job
                should be scheduled on (meta host scheduling).
        @param priority - The job priority (integer).
        @param active - bool, mark this job as running or not in the database?
        @param synchronous - bool, if True use synch_count=2 otherwise use
                synch_count=1.
        @param atomic_group - An atomic group id for this job to schedule on
                or None if atomic scheduling is not required.  Each metahost
                becomes a request to schedule an entire atomic group.
                This does not support creating an active atomic group job.
        """
        assert not (atomic_group and active)  # TODO(gps): support this
        synch_count = synchronous and 2 or 1
        created_on = datetime.datetime(2008, 1, 1)
        status = models.HostQueueEntry.Status.QUEUED
        if active:
            status = models.HostQueueEntry.Status.RUNNING
        job = models.Job.objects.create(
            name='test', owner='my_user', priority=priority,
            synch_count=synch_count, created_on=created_on,
            reboot_before=models.RebootBefore.NEVER)
        for host_id in hosts:
            models.HostQueueEntry.objects.create(job=job, host_id=host_id,
                                                 status=status,
                                                 atomic_group_id=atomic_group)
            models.IneligibleHostQueue.objects.create(job=job, host_id=host_id)
        for label_id in metahosts:
            models.HostQueueEntry.objects.create(job=job, meta_host_id=label_id,
                                                 status=status,
                                                 atomic_group_id=atomic_group)
        if atomic_group and not (metahosts or hosts):
            # Create a single HQE to request the atomic group of hosts even if
            # no metahosts or hosts are supplied.
            models.HostQueueEntry.objects.create(job=job,
                                                 status=status,
                                                 atomic_group_id=atomic_group)
        return job


    def _create_job_simple(self, hosts, use_metahost=False,
                          priority=0, active=False):
        """An alternative interface to _create_job"""
        args = {'hosts' : [], 'metahosts' : []}
        if use_metahost:
            args['metahosts'] = hosts
        else:
            args['hosts'] = hosts
        return self._create_job(priority=priority, active=active, **args)


    def _update_hqe(self, set, where=''):
        query = 'UPDATE host_queue_entries SET ' + set
        if where:
            query += ' WHERE ' + where
        self._do_query(query)


class DBObjectTest(BaseSchedulerTest):
    # It may seem odd to subclass BaseSchedulerTest for this but it saves us
    # duplicating some setup work for what we want to test.


    def test_compare_fields_in_row(self):
        host = monitor_db.Host(id=1)
        fields = list(host._fields)
        row_data = [getattr(host, fieldname) for fieldname in fields]
        self.assertEqual({}, host._compare_fields_in_row(row_data))
        row_data[fields.index('hostname')] = 'spam'
        self.assertEqual({'hostname': ('host1', 'spam')},
                         host._compare_fields_in_row(row_data))
        row_data[fields.index('id')] = 23
        self.assertEqual({'hostname': ('host1', 'spam'), 'id': (1, 23)},
                         host._compare_fields_in_row(row_data))


    def test_always_query(self):
        host_a = monitor_db.Host(id=2)
        self.assertEqual(host_a.hostname, 'host2')
        self._do_query('UPDATE hosts SET hostname="host2-updated" WHERE id=2')
        host_b = monitor_db.Host(id=2, always_query=True)
        self.assert_(host_a is host_b, 'Cached instance not returned.')
        self.assertEqual(host_a.hostname, 'host2-updated',
                         'Database was not re-queried')

        # If either of these are called, a query was made when it shouldn't be.
        host_a._compare_fields_in_row = lambda _: self.fail('eek! a query!')
        host_a._update_fields_from_row = host_a._compare_fields_in_row 
        host_c = monitor_db.Host(id=2, always_query=False)
        self.assert_(host_a is host_c, 'Cached instance not returned')


    def test_delete(self):
        host = monitor_db.Host(id=3)
        host.delete()
        host = self.assertRaises(monitor_db.DBError, monitor_db.Host, id=3,
                                 always_query=False)
        host = self.assertRaises(monitor_db.DBError, monitor_db.Host, id=3,
                                 always_query=True)

    def test_save(self):
        # Dummy Job to avoid creating a one in the HostQueueEntry __init__.
        class MockJob(object):
            def __init__(self, id):
                pass
            def tag(self):
                return 'MockJob'
        self.god.stub_with(monitor_db, 'Job', MockJob)
        hqe = monitor_db.HostQueueEntry(
                new_record=True,
                row=[0, 1, 2, 'Queued', None, 0, 0, 0, '.', None, False])
        hqe.save()
        new_id = hqe.id
        # Force a re-query and verify that the correct data was stored.
        monitor_db.DBObject._clear_instance_cache()
        hqe = monitor_db.HostQueueEntry(id=new_id)
        self.assertEqual(hqe.id, new_id)
        self.assertEqual(hqe.job_id, 1)
        self.assertEqual(hqe.host_id, 2)
        self.assertEqual(hqe.status, 'Queued')
        self.assertEqual(hqe.meta_host, None)
        self.assertEqual(hqe.active, False)
        self.assertEqual(hqe.complete, False)
        self.assertEqual(hqe.deleted, False)
        self.assertEqual(hqe.execution_subdir, '.')
        self.assertEqual(hqe.atomic_group_id, None)


class DispatcherSchedulingTest(BaseSchedulerTest):
    _jobs_scheduled = []


    def tearDown(self):
        super(DispatcherSchedulingTest, self).tearDown()


    def _set_monitor_stubs(self):
        super(DispatcherSchedulingTest, self)._set_monitor_stubs()

        def job_run_stub(job_self, queue_entry):
            """Return a dummy for testing.  Called by HostQueueEntry.run()."""
            self._record_job_scheduled(job_self.id, queue_entry.host.id)
            queue_entry.set_status('Starting')
            return DummyAgent()

        self.god.stub_with(monitor_db.Job, 'run', job_run_stub)

        def hqe_queue_log_record_stub(self, log_line):
            """No-Op to avoid calls down to the _drone_manager during tests."""

        self.god.stub_with(monitor_db.HostQueueEntry, 'queue_log_record',
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
        self._do_query('UPDATE host_queue_entries SET '
                       'meta_host=host_id, host_id=NULL '
                       'WHERE job_id IN ' + sql_tuple)


    def _lock_host(self, host_id):
        self._do_query('UPDATE hosts SET locked=1 WHERE id=' +
                       str(host_id))


    def setUp(self):
        super(DispatcherSchedulingTest, self).setUp()
        self._jobs_scheduled = []


    def _test_basic_scheduling_helper(self, use_metahosts):
        'Basic nonmetahost scheduling'
        self._create_job_simple([1], use_metahosts)
        self._create_job_simple([2], use_metahosts)
        self._dispatcher._schedule_new_jobs()
        self._assert_job_scheduled_on(1, 1)
        self._assert_job_scheduled_on(2, 2)
        self._check_for_extra_schedulings()


    def _test_priorities_helper(self, use_metahosts):
        'Test prioritization ordering'
        self._create_job_simple([1], use_metahosts)
        self._create_job_simple([2], use_metahosts)
        self._create_job_simple([1,2], use_metahosts)
        self._create_job_simple([1], use_metahosts, priority=1)
        self._dispatcher._schedule_new_jobs()
        self._assert_job_scheduled_on(4, 1) # higher priority
        self._assert_job_scheduled_on(2, 2) # earlier job over later
        self._check_for_extra_schedulings()


    def _test_hosts_ready_helper(self, use_metahosts):
        """
        Only hosts that are status=Ready, unlocked and not invalid get
        scheduled.
        """
        self._create_job_simple([1], use_metahosts)
        self._do_query('UPDATE hosts SET status="Running" WHERE id=1')
        self._dispatcher._schedule_new_jobs()
        self._check_for_extra_schedulings()

        self._do_query('UPDATE hosts SET status="Ready", locked=1 '
                       'WHERE id=1')
        self._dispatcher._schedule_new_jobs()
        self._check_for_extra_schedulings()

        self._do_query('UPDATE hosts SET locked=0, invalid=1 '
                       'WHERE id=1')
        self._dispatcher._schedule_new_jobs()
        if not use_metahosts:
            self._assert_job_scheduled_on(1, 1)
        self._check_for_extra_schedulings()


    def _test_hosts_idle_helper(self, use_metahosts):
        'Only idle hosts get scheduled'
        self._create_job(hosts=[1], active=True)
        self._create_job_simple([1], use_metahosts)
        self._dispatcher._schedule_new_jobs()
        self._check_for_extra_schedulings()


    def _test_obey_ACLs_helper(self, use_metahosts):
        self._do_query('DELETE FROM acl_groups_hosts WHERE host_id=1')
        self._create_job_simple([1], use_metahosts)
        self._dispatcher._schedule_new_jobs()
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


    def test_non_metahost_on_invalid_host(self):
        """
        Non-metahost entries can get scheduled on invalid hosts (this is how
        one-time hosts work).
        """
        self._do_query('UPDATE hosts SET invalid=1')
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
        self._dispatcher._schedule_new_jobs()
        self._check_for_extra_schedulings()


    def test_only_if_needed_labels_schedules(self):
        job = self._setup_test_only_if_needed_labels()
        job.dependency_labels.add(self.label3)
        self._dispatcher._schedule_new_jobs()
        self._assert_job_scheduled_on(1, 1)
        self._check_for_extra_schedulings()


    def test_only_if_needed_labels_via_metahost(self):
        job = self._setup_test_only_if_needed_labels()
        job.dependency_labels.add(self.label3)
        # should also work if the metahost is the only_if_needed label
        self._do_query('DELETE FROM jobs_dependency_labels')
        self._create_job(metahosts=[3])
        self._dispatcher._schedule_new_jobs()
        self._assert_job_scheduled_on(2, 1)
        self._check_for_extra_schedulings()


    def test_nonmetahost_over_metahost(self):
        """
        Non-metahost entries should take priority over metahost entries
        for the same host
        """
        self._create_job(metahosts=[1])
        self._create_job(hosts=[1])
        self._dispatcher._schedule_new_jobs()
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
        self._dispatcher._schedule_new_jobs()
        self._check_for_extra_schedulings()


    # TODO(gps): These should probably live in their own TestCase class
    # specific to testing HostScheduler methods directly.  It was convenient
    # to put it here for now to share existing test environment setup code.
    def test_HostScheduler_check_atomic_group_labels(self):
        normal_job = self._create_job(metahosts=[0])
        atomic_job = self._create_job(atomic_group=1)
        # Indirectly initialize the internal state of the host scheduler.
        self._dispatcher._refresh_pending_queue_entries()

        atomic_hqe = monitor_db.HostQueueEntry(id=atomic_job.id)
        normal_hqe = monitor_db.HostQueueEntry(id=normal_job.id)

        host_scheduler = self._dispatcher._host_scheduler
        self.assertTrue(host_scheduler._check_atomic_group_labels(
                [self.label4.id], atomic_hqe))
        self.assertFalse(host_scheduler._check_atomic_group_labels(
                [self.label4.id], normal_hqe))
        self.assertFalse(host_scheduler._check_atomic_group_labels(
                [self.label5.id, self.label6.id, self.label7.id], normal_hqe))
        self.assertTrue(host_scheduler._check_atomic_group_labels(
                [self.label4.id, self.label6.id], atomic_hqe))
        self.assertRaises(monitor_db.SchedulerError,
                          host_scheduler._check_atomic_group_labels,
                          [self.label4.id, self.label5.id],
                          atomic_hqe)


    def test_HostScheduler_get_host_atomic_group_id(self):
        self._create_job(metahosts=[self.label6.id])
        # Indirectly initialize the internal state of the host scheduler.
        self._dispatcher._refresh_pending_queue_entries()

        # Test the host scheduler
        host_scheduler = self._dispatcher._host_scheduler
        self.assertRaises(monitor_db.SchedulerError,
                          host_scheduler._get_host_atomic_group_id,
                          [self.label4.id, self.label5.id])
        self.assertEqual(None, host_scheduler._get_host_atomic_group_id([]))
        self.assertEqual(None, host_scheduler._get_host_atomic_group_id(
                [self.label3.id, self.label7.id, self.label6.id]))
        self.assertEqual(1, host_scheduler._get_host_atomic_group_id(
                [self.label4.id, self.label7.id, self.label6.id]))
        self.assertEqual(1, host_scheduler._get_host_atomic_group_id(
                [self.label7.id, self.label5.id]))


    def test_atomic_group_hosts_blocked_from_non_atomic_jobs(self):
        # Create a job scheduled to run on label6.
        self._create_job(metahosts=[self.label6.id])
        self._dispatcher._schedule_new_jobs()
        # label6 only has hosts that are in atomic groups associated with it,
        # there should be no scheduling.
        self._check_for_extra_schedulings()


    def test_atomic_group_hosts_blocked_from_non_atomic_jobs_explicit(self):
        # Create a job scheduled to run on label5.  This is an atomic group
        # label but this job does not request atomic group scheduling.
        self._create_job(metahosts=[self.label5.id])
        self._dispatcher._schedule_new_jobs()
        # label6 only has hosts that are in atomic groups associated with it,
        # there should be no scheduling.
        self._check_for_extra_schedulings()


    def test_atomic_group_scheduling_basics(self):
        # Create jobs scheduled to run on an atomic group.
        job_a = self._create_job(synchronous=True, metahosts=[self.label4.id],
                         atomic_group=1)
        job_b = self._create_job(synchronous=True, metahosts=[self.label5.id],
                         atomic_group=1)
        self._dispatcher._schedule_new_jobs()
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
        self._dispatcher._schedule_new_jobs()
        self._assert_job_scheduled_on_number_of(onehost_job.id, (5, 6, 7), 1)
        self._check_for_extra_schedulings()

        # No more atomic groups have hosts available, no more jobs should
        # be scheduled.
        self._create_job(atomic_group=1)
        self._dispatcher._schedule_new_jobs()
        self._check_for_extra_schedulings()


    def test_atomic_group_scheduling_obeys_acls(self):
        # Request scheduling on a specific atomic label but be denied by ACLs.
        self._do_query('DELETE FROM acl_groups_hosts WHERE host_id in (8,9)')
        job = self._create_job(metahosts=[self.label5.id], atomic_group=1)
        self._dispatcher._schedule_new_jobs()
        self._check_for_extra_schedulings()


    def test_atomic_group_scheduling_dependency_label_exclude(self):
        # A dependency label that matches no hosts in the atomic group.
        job_a = self._create_job(atomic_group=1)
        job_a.dependency_labels.add(self.label3)
        self._dispatcher._schedule_new_jobs()
        self._check_for_extra_schedulings()


    def test_atomic_group_scheduling_metahost_dependency_label_exclude(self):
        # A metahost and dependency label that excludes too many hosts.
        job_b = self._create_job(synchronous=True, metahosts=[self.label4.id],
                                 atomic_group=1)
        job_b.dependency_labels.add(self.label7)
        self._dispatcher._schedule_new_jobs()
        self._check_for_extra_schedulings()


    def test_atomic_group_scheduling_dependency_label_match(self):
        # A dependency label that exists on enough atomic group hosts in only
        # one of the two atomic group labels.
        job_c = self._create_job(synchronous=True, atomic_group=1)
        job_c.dependency_labels.add(self.label7)
        self._dispatcher._schedule_new_jobs()
        self._assert_job_scheduled_on_number_of(job_c.id, (8, 9), 2)
        self._check_for_extra_schedulings()


    def test_atomic_group_scheduling_no_metahost(self):
        # Force it to schedule on the other group for a reliable test.
        self._do_query('UPDATE hosts SET invalid=1 WHERE id=9')
        # An atomic job without a metahost.
        job = self._create_job(synchronous=True, atomic_group=1)
        self._dispatcher._schedule_new_jobs()
        self._assert_job_scheduled_on_number_of(job.id, (5, 6, 7), 2)
        self._check_for_extra_schedulings()


    def test_atomic_group_scheduling_partial_group(self):
        # Make one host in labels[3] unavailable so that there are only two
        # hosts left in the group.
        self._do_query('UPDATE hosts SET status="Repair Failed" WHERE id=5')
        job = self._create_job(synchronous=True, metahosts=[self.label4.id],
                         atomic_group=1)
        self._dispatcher._schedule_new_jobs()
        # Verify that it was scheduled on the 2 ready hosts in that group.
        self._assert_job_scheduled_on(job.id, 6)
        self._assert_job_scheduled_on(job.id, 7)
        self._check_for_extra_schedulings()


    def test_atomic_group_scheduling_not_enough_available(self):
        # Mark some hosts in each atomic group label as not usable.
        # One host running, another invalid in the first group label.
        self._do_query('UPDATE hosts SET status="Running" WHERE id=5')
        self._do_query('UPDATE hosts SET invalid=1 WHERE id=6')
        # One host invalid in the second group label.
        self._do_query('UPDATE hosts SET invalid=1 WHERE id=9')
        # Nothing to schedule when no group label has enough (2) good hosts..
        self._create_job(atomic_group=1, synchronous=True)
        self._dispatcher._schedule_new_jobs()
        # There are not enough hosts in either atomic group,
        # No more scheduling should occur.
        self._check_for_extra_schedulings()

        # Now create an atomic job that has a synch count of 1.  It should
        # schedule on exactly one of the hosts.
        onehost_job = self._create_job(atomic_group=1)
        self._dispatcher._schedule_new_jobs()
        self._assert_job_scheduled_on_number_of(onehost_job.id, (7, 8), 1)


    def test_atomic_group_scheduling_no_valid_hosts(self):
        self._do_query('UPDATE hosts SET invalid=1 WHERE id in (8,9)')
        self._create_job(synchronous=True, metahosts=[self.label5.id],
                         atomic_group=1)
        self._dispatcher._schedule_new_jobs()
        # no hosts in the selected group and label are valid.  no schedulings.
        self._check_for_extra_schedulings()


    def test_atomic_group_scheduling_metahost_works(self):
        # Test that atomic group scheduling also obeys metahosts.
        self._create_job(metahosts=[0], atomic_group=1)
        self._dispatcher._schedule_new_jobs()
        # There are no atomic group hosts that also have that metahost.
        self._check_for_extra_schedulings()

        job_b = self._create_job(metahosts=[self.label5.id], atomic_group=1)
        self._dispatcher._schedule_new_jobs()
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
        self._dispatcher._schedule_new_jobs()
        # No scheduling should occur as all desired hosts were ineligible.
        self._check_for_extra_schedulings()


    def test_atomic_group_scheduling_fail(self):
        # If synch_count is > the atomic group number of machines, the job
        # should be aborted immediately.
        model_job = self._create_job(synchronous=True, atomic_group=1)
        model_job.synch_count = 4
        model_job.save()
        job = monitor_db.Job(id=model_job.id)
        self._dispatcher._schedule_new_jobs()
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

        self._dispatcher._schedule_new_jobs()
        self._check_for_extra_schedulings()


    def test_schedule_directly_on_atomic_group_host_fail(self):
        # Scheduling a job directly on hosts in an atomic group must
        # fail to avoid users inadvertently holding up the use of an
        # entire atomic group by using the machines individually.
        job = self._create_job(hosts=[5])
        self._dispatcher._schedule_new_jobs()
        self._check_for_extra_schedulings()


    def test_schedule_directly_on_atomic_group_host(self):
        # Scheduling a job directly on one host in an atomic group will
        # work when the atomic group is listed on the HQE in addition
        # to the host (assuming the sync count is 1).
        job = self._create_job(hosts=[5], atomic_group=1)
        self._dispatcher._schedule_new_jobs()
        self._assert_job_scheduled_on(job.id, 5)
        self._check_for_extra_schedulings()


    def test_schedule_directly_on_atomic_group_hosts_sync2(self):
        job = self._create_job(hosts=[5,8], atomic_group=1, synchronous=True)
        self._dispatcher._schedule_new_jobs()
        self._assert_job_scheduled_on(job.id, 5)
        self._assert_job_scheduled_on(job.id, 8)
        self._check_for_extra_schedulings()


    def test_schedule_directly_on_atomic_group_hosts_wrong_group(self):
        job = self._create_job(hosts=[5,8], atomic_group=2, synchronous=True)
        self._dispatcher._schedule_new_jobs()
        self._check_for_extra_schedulings()


    def test_only_schedule_queued_entries(self):
        self._create_job(metahosts=[1])
        self._update_hqe(set='active=1, host_id=2')
        self._dispatcher._schedule_new_jobs()
        self._check_for_extra_schedulings()


    def test_no_ready_hosts(self):
        self._create_job(hosts=[1])
        self._do_query('UPDATE hosts SET status="Repair Failed"')
        self._dispatcher._schedule_new_jobs()
        self._check_for_extra_schedulings()


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

        def fake_max_runnable_processes(fake_self):
            running = sum(agent.num_processes
                          for agent in self._agents
                          if agent.is_running())
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
            self.assert_(self._agents[i].is_running() == is_started,
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
        self._agents[0].num_processes = 3
        self._run_a_few_cycles()
        self._assert_agents_started([0])
        self._assert_agents_not_started([1])


    def test_large_agent_starvation(self):
        """
        Ensure large agents don't get starved by lower-priority agents.
        """
        self._setup_some_agents(3)
        self._agents[1].num_processes = 3
        self._run_a_few_cycles()
        self._assert_agents_started([0])
        self._assert_agents_not_started([1, 2])

        self._agents[0].set_done(True)
        self._run_a_few_cycles()
        self._assert_agents_started([1])
        self._assert_agents_not_started([2])


    def test_zero_process_agent(self):
        self._setup_some_agents(5)
        self._agents[4].num_processes = 0
        self._run_a_few_cycles()
        self._assert_agents_started([0, 1, 2, 4])
        self._assert_agents_not_started([3])


class FindAbortTest(BaseSchedulerTest):
    """
    Test the dispatcher abort functionality.
    """
    def _check_host_agent(self, agent, host_id):
        self.assert_(isinstance(agent, monitor_db.Agent))
        tasks = list(agent.queue.queue)
        self.assertEquals(len(tasks), 2)
        cleanup, verify = tasks

        self.assert_(isinstance(cleanup, monitor_db.CleanupTask))
        self.assertEquals(cleanup.host.id, host_id)

        self.assert_(isinstance(verify, monitor_db.VerifyTask))
        self.assertEquals(verify.host.id, host_id)


    def _check_agents(self, agents):
        agents = list(agents)
        self.assertEquals(len(agents), 3)
        self.assertEquals(agents[0], self._agent)
        self._check_host_agent(agents[1], 1)
        self._check_host_agent(agents[2], 2)


    def _common_setup(self):
        self._create_job(hosts=[1, 2])
        self._update_hqe(set='aborted=1')
        self._agent = self.god.create_mock_class(monitor_db.Agent, 'old_agent')
        _set_host_and_qe_ids(self._agent, [1, 2])
        self._agent.abort.expect_call()
        self._agent.abort.expect_call() # gets called once for each HQE
        self._dispatcher.add_agent(self._agent)


    def test_find_aborting(self):
        self._common_setup()
        self._dispatcher._find_aborting()
        self.god.check_playback()


    def test_find_aborting_verifying(self):
        self._common_setup()
        self._update_hqe(set='active=1, status="Verifying"')

        self._dispatcher._find_aborting()

        self._check_agents(self._dispatcher._agents)
        self.god.check_playback()


class JobTimeoutTest(BaseSchedulerTest):
    def _test_synch_start_timeout_helper(self, expect_abort,
                                         set_created_on=True, set_active=True,
                                         set_acl=True):
        scheduler_config.config.synch_job_start_timeout_minutes = 60
        job = self._create_job(hosts=[1, 2])
        if set_active:
            hqe = job.hostqueueentry_set.filter(host__id=1)[0]
            hqe.status = 'Pending'
            hqe.active = 1
            hqe.save()

        everyone_acl = models.AclGroup.smart_get('Everyone')
        host1 = models.Host.smart_get(1)
        if set_acl:
            everyone_acl.hosts.add(host1)
        else:
            everyone_acl.hosts.remove(host1)

        job.created_on = datetime.datetime.now()
        if set_created_on:
            job.created_on -= datetime.timedelta(minutes=100)
        job.save()

        cleanup = self._dispatcher._periodic_cleanup
        cleanup._abort_jobs_past_synch_start_timeout()

        for hqe in job.hostqueueentry_set.all():
            self.assertEquals(hqe.aborted, expect_abort)


    def test_synch_start_timeout_helper(self):
        # no abort if any of the condition aren't met
        self._test_synch_start_timeout_helper(False, set_created_on=False)
        self._test_synch_start_timeout_helper(False, set_active=False)
        self._test_synch_start_timeout_helper(False, set_acl=False)
        # abort if all conditions are met
        self._test_synch_start_timeout_helper(True)


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
        self.god.stub_function(email_manager.manager, 'enqueue_notify_email')

        self.pidfile_id = object()

        (self.mock_drone_manager.get_pidfile_id_from
             .expect_call(self.execution_tag,
                          pidfile_name=monitor_db._AUTOSERV_PID_FILE)
             .and_return(self.pidfile_id))
        self.mock_drone_manager.register_pidfile.expect_call(self.pidfile_id)

        self.monitor = monitor_db.PidfileRunMonitor()
        self.monitor.attach_to_existing_process(self.execution_tag)


    def tearDown(self):
        self.god.unstub_all()


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
        self.set_complete(123, use_second_read=True) # pidfile gets read again
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
        email_manager.manager.enqueue_notify_email.expect_call(
            mock.is_string_comparator(), mock.is_string_comparator())
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
        email_manager.manager.enqueue_notify_email.expect_call(
            mock.is_string_comparator(), mock.is_string_comparator())
        self.monitor._start_time = time.time() - monitor_db.PIDFILE_TIMEOUT - 1
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
        _set_host_and_qe_ids(task)
        return task

    def _create_agent(self, tasks):
        agent = monitor_db.Agent(tasks)
        agent.dispatcher = self._dispatcher
        return agent


    def _finish_agent(self, agent):
        while not agent.is_done():
            agent.tick()


    def test_agent(self):
        task1 = self._create_mock_task('task1')
        task2 = self._create_mock_task('task2')
        task3 = self._create_mock_task('task3')

        task1.start.expect_call()
        task1.is_done.expect_call().and_return(False)
        task1.poll.expect_call()
        task1.is_done.expect_call().and_return(True)
        task1.is_done.expect_call().and_return(True)
        task1.success = True

        task2.start.expect_call()
        task2.is_done.expect_call().and_return(True)
        task2.is_done.expect_call().and_return(True)
        task2.success = False
        task2.failure_tasks = [task3]

        self._dispatcher.add_agent.expect_call(IsAgentWithTask(task3))

        agent = self._create_agent([task1, task2])
        agent.start()
        self._finish_agent(agent)
        self.god.check_playback()


    def _test_agent_abort_helper(self, ignore_abort=False):
        task1 = self._create_mock_task('task1')
        task2 = self._create_mock_task('task2')
        task1.start.expect_call()
        task1.is_done.expect_call().and_return(False)
        task1.poll.expect_call()
        task1.is_done.expect_call().and_return(False)
        task1.abort.expect_call()
        if ignore_abort:
            task1.aborted = False # task ignores abort; execution continues

            task1.is_done.expect_call().and_return(True)
            task1.is_done.expect_call().and_return(True)
            task1.success = True

            task2.start.expect_call()
            task2.is_done.expect_call().and_return(True)
            task2.is_done.expect_call().and_return(True)
            task2.success = True
        else:
            task1.aborted = True # execution halts, no further expectations

        agent = self._create_agent([task1, task2])
        agent.start()
        agent.tick()
        agent.abort()
        self._finish_agent(agent)
        self.god.check_playback()


    def test_agent_abort(self):
        self._test_agent_abort_helper()
        self._test_agent_abort_helper(True)


    def test_agent_abort_before_started(self):
        task = self._create_mock_task('task')
        agent = self._create_agent([task])
        agent.abort()
        agent.start()
        self._finish_agent(agent)
        self.god.check_playback()


class AgentTasksTest(unittest.TestCase):
    TEMP_DIR = '/abspath/tempdir'
    RESULTS_DIR = '/results/dir'
    HOSTNAME = 'myhost'
    DUMMY_PROCESS = object()
    HOST_PROTECTION = host_protections.default
    PIDFILE_ID = object()
    JOB_OWNER = 'test_owner'
    JOB_NAME = 'test_job_name'
    JOB_AUTOSERV_PARAMS = set(['-u', JOB_OWNER, '-l', JOB_NAME])

    def setUp(self):
        self.god = mock.mock_god()
        self.god.stub_with(drone_manager.DroneManager, 'get_temporary_path',
                           mock.mock_function('get_temporary_path',
                                              default_return_val='tempdir'))
        self.god.stub_function(drone_manager.DroneManager,
                               'copy_results_on_drone')
        self.god.stub_function(drone_manager.DroneManager,
                               'copy_to_results_repository')
        self.god.stub_function(drone_manager.DroneManager,
                               'get_pidfile_id_from')

        def dummy_absolute_path(self, path):
            return '/abspath/' + path
        self.god.stub_with(drone_manager.DroneManager, 'absolute_path',
                           dummy_absolute_path)

        self.god.stub_class_method(monitor_db.PidfileRunMonitor, 'run')
        self.god.stub_class_method(monitor_db.PidfileRunMonitor, 'exit_code')
        self.god.stub_class_method(monitor_db.PidfileRunMonitor, 'get_process')
        def mock_has_process(unused):
            return True
        self.god.stub_with(monitor_db.PidfileRunMonitor, 'has_process',
                           mock_has_process)
        self.host = self.god.create_mock_class(monitor_db.Host, 'host')
        self.host.id = 1
        self.host.hostname = self.HOSTNAME
        self.host.protection = self.HOST_PROTECTION
        self.queue_entry = self.god.create_mock_class(
            monitor_db.HostQueueEntry, 'queue_entry')
        self.job = self.god.create_mock_class(monitor_db.Job, 'job')
        self.job.owner = self.JOB_OWNER
        self.job.name = self.JOB_NAME
        self.queue_entry.id = 1
        self.queue_entry.job = self.job
        self.queue_entry.host = self.host
        self.queue_entry.meta_host = None
        self._dispatcher = self.god.create_mock_class(monitor_db.Dispatcher,
                                                      'dispatcher')


    def tearDown(self):
        self.god.unstub_all()


    def run_task(self, task, success):
        """
        Do essentially what an Agent would do, but protect againt
        infinite looping from test errors.
        """
        if not getattr(task, 'agent', None):
            task.agent = object()
        task.start()
        count = 0
        while not task.is_done():
            count += 1
            if count > 10:
                print 'Task failed to finish'
                # in case the playback has clues to why it
                # failed
                self.god.check_playback()
                self.fail()
            task.poll()
        self.assertEquals(task.success, success)


    def setup_run_monitor(self, exit_status, copy_log_file=True):
        monitor_db.PidfileRunMonitor.run.expect_call(
            mock.is_instance_comparator(list),
            'tempdir',
            nice_level=monitor_db.AUTOSERV_NICE_LEVEL,
            log_file=mock.anything_comparator(),
            pidfile_name=monitor_db._AUTOSERV_PID_FILE,
            paired_with_pidfile=None)
        monitor_db.PidfileRunMonitor.exit_code.expect_call()
        monitor_db.PidfileRunMonitor.exit_code.expect_call().and_return(
            exit_status)

        if copy_log_file:
            self._setup_move_logfile()


    def _setup_move_logfile(self, copy_on_drone=False,
                            include_destination=False):
        monitor_db.PidfileRunMonitor.get_process.expect_call().and_return(
            self.DUMMY_PROCESS)
        if copy_on_drone:
            self.queue_entry.execution_tag.expect_call().and_return('tag')
            drone_manager.DroneManager.copy_results_on_drone.expect_call(
                self.DUMMY_PROCESS, source_path=mock.is_string_comparator(),
                destination_path=mock.is_string_comparator())
        elif include_destination:
            drone_manager.DroneManager.copy_to_results_repository.expect_call(
                self.DUMMY_PROCESS, mock.is_string_comparator(),
                destination_path=mock.is_string_comparator())
        else:
            drone_manager.DroneManager.copy_to_results_repository.expect_call(
                self.DUMMY_PROCESS, mock.is_string_comparator())


    def _test_repair_task_helper(self, success):
        self.host.set_status.expect_call('Repairing')
        if success:
            self.setup_run_monitor(0)
            self.host.set_status.expect_call('Ready')
        else:
            self.setup_run_monitor(1)
            self.host.set_status.expect_call('Repair Failed')

        task = monitor_db.RepairTask(self.host)
        self.assertEquals(task.failure_tasks, [])
        self.run_task(task, success)

        expected_protection = host_protections.Protection.get_string(
            host_protections.default)
        expected_protection = host_protections.Protection.get_attr_name(
            expected_protection)

        self.assertTrue(set(task.cmd) >=
                        set([monitor_db._autoserv_path, '-p', '-R', '-m',
                             self.HOSTNAME, '-r', self.TEMP_DIR,
                             '--host-protection', expected_protection]))
        self.god.check_playback()


    def test_repair_task(self):
        self._test_repair_task_helper(True)
        self._test_repair_task_helper(False)


    def test_repair_task_with_queue_entry(self):
        self.god.stub_class(monitor_db, 'FinalReparseTask')
        self.god.stub_class(monitor_db, 'Agent')
        self.god.stub_class_method(monitor_db.TaskWithJobKeyvals,
                                   '_write_keyval_after_job')
        agent = DummyAgent()
        agent.dispatcher = self._dispatcher

        self.host.set_status.expect_call('Repairing')
        self.queue_entry.requeue.expect_call()
        self.setup_run_monitor(1)
        self.host.set_status.expect_call('Repair Failed')
        self.queue_entry.update_from_database.expect_call()
        self.queue_entry.set_execution_subdir.expect_call()
        monitor_db.TaskWithJobKeyvals._write_keyval_after_job.expect_call(
            'job_queued', mock.is_instance_comparator(int))
        monitor_db.TaskWithJobKeyvals._write_keyval_after_job.expect_call(
            'job_finished', mock.is_instance_comparator(int))
        self._setup_move_logfile(copy_on_drone=True)
        self.queue_entry.execution_tag.expect_call().and_return('tag')
        self._setup_move_logfile()
        reparse_task = monitor_db.FinalReparseTask.expect_new(
            [self.queue_entry])
        reparse_agent = monitor_db.Agent.expect_new([reparse_task],
                                                    num_processes=0)
        self._dispatcher.add_agent.expect_call(reparse_agent)
        self.queue_entry.handle_host_failure.expect_call()

        task = monitor_db.RepairTask(self.host, self.queue_entry)
        task.agent = agent
        self.queue_entry.status = 'Queued'
        self.job.created_on = datetime.datetime(2009, 1, 1)
        self.run_task(task, False)
        self.assertTrue(set(task.cmd) >= self.JOB_AUTOSERV_PARAMS)
        self.god.check_playback()


    def setup_verify_expects(self, success, use_queue_entry):
        if use_queue_entry:
            self.queue_entry.set_status.expect_call('Verifying')
        self.host.set_status.expect_call('Verifying')
        if success:
            self.setup_run_monitor(0)
            self.host.set_status.expect_call('Ready')
        else:
            self.setup_run_monitor(1)
            if use_queue_entry and not self.queue_entry.meta_host:
                self.queue_entry.set_execution_subdir.expect_call()
                self.queue_entry.execution_tag.expect_call().and_return('tag')
                self._setup_move_logfile(include_destination=True)


    def _check_verify_failure_tasks(self, verify_task):
        self.assertEquals(len(verify_task.failure_tasks), 1)
        repair_task = verify_task.failure_tasks[0]
        self.assert_(isinstance(repair_task, monitor_db.RepairTask))
        self.assertEquals(verify_task.host, repair_task.host)
        if verify_task.queue_entry:
            self.assertEquals(repair_task.queue_entry_to_fail,
                              verify_task.queue_entry)
        else:
            self.assertEquals(repair_task.queue_entry_to_fail, None)


    def _test_verify_task_helper(self, success, use_queue_entry=False,
                                 use_meta_host=False):
        self.setup_verify_expects(success, use_queue_entry)

        if use_queue_entry:
            task = monitor_db.VerifyTask(queue_entry=self.queue_entry)
        else:
            task = monitor_db.VerifyTask(host=self.host)
        self._check_verify_failure_tasks(task)
        self.run_task(task, success)
        self.assertTrue(set(task.cmd) >=
                        set([monitor_db._autoserv_path, '-p', '-v', '-m',
                             self.HOSTNAME, '-r', self.TEMP_DIR]))
        if use_queue_entry:
            self.assertTrue(set(task.cmd) >= self.JOB_AUTOSERV_PARAMS)
        self.god.check_playback()


    def test_verify_task_with_host(self):
        self._test_verify_task_helper(True)
        self._test_verify_task_helper(False)


    def test_verify_task_with_queue_entry(self):
        self._test_verify_task_helper(True, use_queue_entry=True)
        self._test_verify_task_helper(False, use_queue_entry=True)


    def test_verify_task_with_metahost(self):
        self.queue_entry.meta_host = 1
        self.test_verify_task_with_queue_entry()


    def _setup_post_job_task_expects(self, autoserv_success, hqe_status,
                                     hqe_aborted=False):
        self.queue_entry.execution_tag.expect_call().and_return('tag')
        self.pidfile_monitor = monitor_db.PidfileRunMonitor.expect_new()
        self.pidfile_monitor.pidfile_id = self.PIDFILE_ID
        self.pidfile_monitor.attach_to_existing_process.expect_call('tag')
        if autoserv_success:
            code = 0
        else:
            code = 1
        self.queue_entry.update_from_database.expect_call()
        self.queue_entry.aborted = hqe_aborted
        if not hqe_aborted:
            self.pidfile_monitor.exit_code.expect_call().and_return(code)

        self.queue_entry.set_status.expect_call(hqe_status)


    def _setup_pre_parse_expects(self, autoserv_success):
        self._setup_post_job_task_expects(autoserv_success, 'Parsing')


    def _setup_post_parse_expects(self, autoserv_success):
        if autoserv_success:
            status = 'Completed'
        else:
            status = 'Failed'
        self.queue_entry.set_status.expect_call(status)


    def _setup_post_job_run_monitor(self, pidfile_name):
        self.pidfile_monitor.has_process.expect_call().and_return(True)
        autoserv_pidfile_id = object()
        self.monitor = monitor_db.PidfileRunMonitor.expect_new()
        self.monitor.run.expect_call(
            mock.is_instance_comparator(list),
            'tag',
            nice_level=monitor_db.AUTOSERV_NICE_LEVEL,
            log_file=mock.anything_comparator(),
            pidfile_name=pidfile_name,
            paired_with_pidfile=self.PIDFILE_ID)
        self.monitor.exit_code.expect_call()
        self.monitor.exit_code.expect_call().and_return(0)
        self._expect_copy_results()


    def _expect_copy_results(self, monitor=None, queue_entry=None):
        if monitor is None:
            monitor = self.monitor
        monitor.has_process.expect_call().and_return(True)
        if queue_entry:
            queue_entry.execution_tag.expect_call().and_return('tag')
        monitor.get_process.expect_call().and_return(self.DUMMY_PROCESS)
        drone_manager.DroneManager.copy_to_results_repository.expect_call(
                self.DUMMY_PROCESS, mock.is_string_comparator())


    def _test_final_reparse_task_helper(self, autoserv_success=True):
        self._setup_pre_parse_expects(autoserv_success)
        self._setup_post_job_run_monitor(monitor_db._PARSER_PID_FILE)
        self._setup_post_parse_expects(autoserv_success)

        task = monitor_db.FinalReparseTask([self.queue_entry])
        self.run_task(task, True)

        self.god.check_playback()
        cmd = [monitor_db._parser_path, '--write-pidfile', '-l', '2', '-r',
               '-o', '/abspath/tag']
        self.assertEquals(task.cmd, cmd)


    def test_final_reparse_task(self):
        self.god.stub_class(monitor_db, 'PidfileRunMonitor')
        self._test_final_reparse_task_helper()
        self._test_final_reparse_task_helper(autoserv_success=False)


    def test_final_reparse_throttling(self):
        self.god.stub_class(monitor_db, 'PidfileRunMonitor')
        self.god.stub_function(monitor_db.FinalReparseTask,
                               '_can_run_new_parse')

        self._setup_pre_parse_expects(True)
        monitor_db.FinalReparseTask._can_run_new_parse.expect_call().and_return(
            False)
        monitor_db.FinalReparseTask._can_run_new_parse.expect_call().and_return(
            True)
        self._setup_post_job_run_monitor(monitor_db._PARSER_PID_FILE)
        self._setup_post_parse_expects(True)

        task = monitor_db.FinalReparseTask([self.queue_entry])
        self.run_task(task, True)
        self.god.check_playback()


    def _setup_gather_logs_expects(self, hqe_aborted=False):
        self.god.stub_class(monitor_db, 'PidfileRunMonitor')
        self.god.stub_class(monitor_db, 'FinalReparseTask')
        self._setup_post_job_task_expects(True, 'Gathering', hqe_aborted)
        self._setup_post_job_run_monitor('.collect_crashinfo_execute')
        self._expect_copy_results(monitor=self.pidfile_monitor,
                                  queue_entry=self.queue_entry)
        parse_task = monitor_db.FinalReparseTask.expect_new([self.queue_entry])
        _set_host_and_qe_ids(parse_task)
        self._dispatcher.add_agent.expect_call(IsAgentWithTask(parse_task))


    def _run_gather_logs_task(self):
        task = monitor_db.GatherLogsTask(self.job, [self.queue_entry])
        task.agent = DummyAgent()
        task.agent.dispatcher = self._dispatcher
        self.run_task(task, True)
        self.god.check_playback()


    def test_gather_logs_task(self):
        self._setup_gather_logs_expects()
        # no rebooting for this basic test
        self.job.reboot_after = models.RebootAfter.NEVER
        self.host.set_status.expect_call('Ready')

        self._run_gather_logs_task()


    def _setup_gather_task_cleanup_expects(self):
        self.god.stub_class(monitor_db, 'CleanupTask')
        cleanup_task = monitor_db.CleanupTask.expect_new(host=self.host)
        _set_host_and_qe_ids(cleanup_task)
        self._dispatcher.add_agent.expect_call(IsAgentWithTask(cleanup_task))


    def test_gather_logs_reboot_hosts(self):
        self._setup_gather_logs_expects()
        self.job.reboot_after = models.RebootAfter.ALWAYS
        self._setup_gather_task_cleanup_expects()

        self._run_gather_logs_task()


    def test_gather_logs_reboot_on_abort(self):
        self._setup_gather_logs_expects(hqe_aborted=True)
        self.job.reboot_after = models.RebootAfter.NEVER
        self._setup_gather_task_cleanup_expects()

        self._run_gather_logs_task()


    def _test_cleanup_task_helper(self, success, use_queue_entry=False):
        if use_queue_entry:
            self.queue_entry.get_host.expect_call().and_return(self.host)
        self.host.set_status.expect_call('Cleaning')
        if success:
            self.setup_run_monitor(0)
            self.host.set_status.expect_call('Ready')
            self.host.update_field.expect_call('dirty', 0)
        else:
            self.setup_run_monitor(1)
            if use_queue_entry and not self.queue_entry.meta_host:
                self.queue_entry.set_execution_subdir.expect_call()
                self.queue_entry.execution_tag.expect_call().and_return('tag')
                self._setup_move_logfile(include_destination=True)

        if use_queue_entry:
            task = monitor_db.CleanupTask(queue_entry=self.queue_entry)
        else:
            task = monitor_db.CleanupTask(host=self.host)
        self.assertEquals(len(task.failure_tasks), 1)
        repair_task = task.failure_tasks[0]
        self.assert_(isinstance(repair_task, monitor_db.RepairTask))
        if use_queue_entry:
            self.assertEquals(repair_task.queue_entry_to_fail, self.queue_entry)

        self.run_task(task, success)

        self.god.check_playback()
        self.assert_(set(task.cmd) >=
                        set([monitor_db._autoserv_path, '-p', '--cleanup', '-m',
                             self.HOSTNAME, '-r', self.TEMP_DIR]))
        if use_queue_entry:
            self.assertTrue(set(task.cmd) >= self.JOB_AUTOSERV_PARAMS)

    def test_cleanup_task(self):
        self._test_cleanup_task_helper(True)
        self._test_cleanup_task_helper(False)


    def test_cleanup_task_with_queue_entry(self):
        self._test_cleanup_task_helper(False, True)


class JobTest(BaseSchedulerTest):
    def setUp(self):
        super(JobTest, self).setUp()
        self.god.stub_with(
            drone_manager.DroneManager, 'attach_file_to_execution',
            mock.mock_function('attach_file_to_execution',
                               default_return_val='/test/path/tmp/foo'))


    def _setup_directory_expects(self, execution_subdir):
        job_path = os.path.join('.', '1-my_user')
        results_dir = os.path.join(job_path, execution_subdir)


    def _test_run_helper(self, expect_agent=True, expect_starting=False,
                         expect_pending=False):
        if expect_starting:
            expected_status = models.HostQueueEntry.Status.STARTING
        elif expect_pending:
            expected_status = models.HostQueueEntry.Status.PENDING
        else:
            expected_status = models.HostQueueEntry.Status.VERIFYING
        job = monitor_db.Job.fetch('id = 1').next()
        queue_entry = monitor_db.HostQueueEntry.fetch('id = 1').next()
        agent = job.run(queue_entry)

        self.god.check_playback()
        self.assertEquals(models.HostQueueEntry.smart_get(1).status,
                          expected_status)

        if not expect_agent:
            self.assertEquals(agent, None)
            return

        self.assert_(isinstance(agent, monitor_db.Agent))
        tasks = list(agent.queue.queue)
        return tasks


    def _check_verify_task(self, verify_task):
        self.assert_(isinstance(verify_task, monitor_db.VerifyTask))
        self.assertEquals(verify_task.queue_entry.id, 1)


    def _check_pending_task(self, pending_task):
        self.assert_(isinstance(pending_task, monitor_db.SetEntryPendingTask))
        self.assertEquals(pending_task._queue_entry.id, 1)


    def test_run_asynchronous(self):
        self._create_job(hosts=[1, 2])

        tasks = self._test_run_helper()

        self.assertEquals(len(tasks), 2)
        verify_task, pending_task = tasks
        self._check_verify_task(verify_task)
        self._check_pending_task(pending_task)


    def test_run_asynchronous_skip_verify(self):
        job = self._create_job(hosts=[1, 2])
        job.run_verify = False
        job.save()
        self._setup_directory_expects('host1')

        tasks = self._test_run_helper()

        self.assertEquals(len(tasks), 1)
        pending_task = tasks[0]
        self._check_pending_task(pending_task)


    def test_run_synchronous_verify(self):
        self._create_job(hosts=[1, 2], synchronous=True)

        tasks = self._test_run_helper()
        self.assertEquals(len(tasks), 2)
        verify_task, pending_task = tasks
        self._check_verify_task(verify_task)
        self._check_pending_task(pending_task)


    def test_run_synchronous_skip_verify(self):
        job = self._create_job(hosts=[1, 2], synchronous=True)
        job.run_verify = False
        job.save()

        tasks = self._test_run_helper()
        self.assertEquals(len(tasks), 1)
        self._check_pending_task(tasks[0])


    def test_run_synchronous_ready(self):
        self._create_job(hosts=[1, 2], synchronous=True)
        self._update_hqe("status='Pending', execution_subdir=''")
        self._setup_directory_expects('group0')

        tasks = self._test_run_helper(expect_starting=True)
        self.assertEquals(len(tasks), 1)
        queue_task = tasks[0]

        self.assert_(isinstance(queue_task, monitor_db.QueueTask))
        self.assertEquals(queue_task.job.id, 1)
        hqe_ids = [hqe.id for hqe in queue_task.queue_entries]
        self.assertEquals(hqe_ids, [1, 2])


    def test_reboot_before_always(self):
        job = self._create_job(hosts=[1])
        job.reboot_before = models.RebootBefore.ALWAYS
        job.save()

        tasks = self._test_run_helper()
        self.assertEquals(len(tasks), 3)
        cleanup_task = tasks[0]
        self.assert_(isinstance(cleanup_task, monitor_db.CleanupTask))
        self.assertEquals(cleanup_task.host.id, 1)


    def _test_reboot_before_if_dirty_helper(self, expect_reboot):
        job = self._create_job(hosts=[1])
        job.reboot_before = models.RebootBefore.IF_DIRTY
        job.save()

        tasks = self._test_run_helper()
        self.assertEquals(len(tasks), expect_reboot and 3 or 2)
        if expect_reboot:
            cleanup_task = tasks[0]
            self.assert_(isinstance(cleanup_task, monitor_db.CleanupTask))
            self.assertEquals(cleanup_task.host.id, 1)

    def test_reboot_before_if_dirty(self):
        models.Host.smart_get(1).update_object(dirty=True)
        self._test_reboot_before_if_dirty_helper(True)


    def test_reboot_before_not_dirty(self):
        models.Host.smart_get(1).update_object(dirty=False)
        self._test_reboot_before_if_dirty_helper(False)



if __name__ == '__main__':
    unittest.main()
