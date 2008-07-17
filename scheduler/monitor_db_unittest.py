#!/usr/bin/python

import unittest, time, subprocess, os, StringIO, tempfile
import MySQLdb
import common
from autotest_lib.client.common_lib import global_config, host_protections
from autotest_lib.client.common_lib.test_utils import mock

import monitor_db

_DEBUG = False

_TEST_DATA = """
-- create a user and an ACL group
INSERT INTO users (login) VALUES ('my_user');
INSERT INTO acl_groups (name) VALUES ('my_acl');
INSERT INTO acl_groups_users (user_id, acl_group_id) VALUES (1, 1);

-- create some hosts
INSERT INTO hosts (hostname) VALUES ('host1'), ('host2');
-- add hosts to the ACL group
INSERT INTO acl_groups_hosts (host_id, acl_group_id) VALUES
  (1, 1), (2, 1);

-- create a label for each host and one holding both
INSERT INTO labels (name) VALUES ('label1'), ('label2');

-- add hosts to labels
INSERT INTO hosts_labels (host_id, label_id) VALUES
  (1, 1), (2, 2);
"""

class Dummy(object):
    'Dummy object that can have attribute assigned to it'

class DispatcherTest(unittest.TestCase):
    _jobs_scheduled = []
    _job_counter = 0


    def _read_db_info(self):
        config = global_config.global_config
        section = 'AUTOTEST_WEB'
        self._host = config.get_config_value(section, "host")
        self._db_name = config.get_config_value(section, "database")
        self._user = config.get_config_value(section, "user")
        self._password = config.get_config_value(section, "password")


    def _connect_to_db(self, db_name=''):
        self._con = MySQLdb.connect(host=self._host, user=self._user,
                                    passwd=self._password, db=db_name)
        self._con.autocommit(True)
        self._cur = self._con.cursor()


    def _disconnect_from_db(self):
        self._con.close()


    def _do_query(self, sql):
        if _DEBUG:
            print 'SQL:', sql
        self._cur.execute(sql)


    def _do_queries(self, sql_queries):
        for query in sql_queries.split(';'):
            query = query.strip()
            if query:
                self._do_query(query)


    def _get_db_schema(self):
        command = 'mysqldump --no-data -u %s -p%s -h %s %s' % (
            self._user, self._password, self._host, self._db_name)
        proc = subprocess.Popen(command, stdout=subprocess.PIPE,
                                shell=True)
        return proc.communicate()[0]


    def _open_test_db(self, schema):
        self._db_name = 'test_' + self._db_name
        self._connect_to_db()
        self._do_query('CREATE DATABASE ' + self._db_name)
        self._disconnect_from_db()
        self._connect_to_db(self._db_name)
        self._do_queries(schema)


    def _close_test_db(self):
        self._do_query('DROP DATABASE ' + self._db_name)
        self._disconnect_from_db()


    def _fill_in_test_data(self):
        self._do_queries(_TEST_DATA)


    def _set_monitor_stubs(self):
        monitor_db._db = monitor_db.DatabaseConn()
        monitor_db._db.connect(db_name=self._db_name)
        def run_stub(hqe_self, assigned_host=None):
            if hqe_self.meta_host:
                host = assigned_host
            else:
                host = hqe_self.host
            self._record_job_scheduled(hqe_self.job.id, host.id)
            return Dummy()
        monitor_db.HostQueueEntry.run = run_stub


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


    def _check_for_extra_schedulings(self):
        if len(self._jobs_scheduled) != 0:
            self.fail('Extra jobs scheduled: ' +
                      str(self._jobs_scheduled))


    def _create_job(self, hosts=[], metahosts=[], priority=0, active=0):
        self._do_query('INSERT INTO jobs (name, owner, priority) '
                       'VALUES ("test", "my_user", %d)' % priority)
        self._job_counter += 1
        job_id = self._job_counter
        queue_entry_sql = (
            'INSERT INTO host_queue_entries '
            '(job_id, priority, host_id, meta_host, active) '
            'VALUES (%d, %d, %%s, %%s, %d)' %
            (job_id, priority, active))
        for host_id in hosts:
            self._do_query(queue_entry_sql % (host_id, 'NULL'))
            self._do_query('INSERT INTO ineligible_host_queues '
                           '(job_id, host_id) VALUES (%d, %d)' %
                           (job_id, host_id))
        for label_id in metahosts:
            self._do_query(queue_entry_sql % ('NULL', label_id))


    def _create_job_simple(self, hosts, use_metahost=False,
                          priority=0, active=0):
        'An alternative interface to _create_job'
        args = {'hosts' : [], 'metahosts' : []}
        if use_metahost:
            args['metahosts'] = hosts
        else:
            args['hosts'] = hosts
        self._create_job(priority=priority, active=active, **args)


    def _convert_jobs_to_metahosts(self, *job_ids):
        sql_tuple = '(' + ','.join(str(i) for i in job_ids) + ')'
        self._do_query('UPDATE host_queue_entries SET '
                       'meta_host=host_id, host_id=NULL '
                       'WHERE job_id IN ' + sql_tuple)


    def _lock_host(self, host_id):
        self._do_query('UPDATE hosts SET locked=1 WHERE id=' +
                       str(host_id))


    def setUp(self):
        self._read_db_info()
        schema = self._get_db_schema()
        self._open_test_db(schema)
        self._fill_in_test_data()
        self._set_monitor_stubs()
        self._dispatcher = monitor_db.Dispatcher()
        self._jobs_scheduled = []
        self._job_counter = 0


    def tearDown(self):
        self._close_test_db()


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
        self._create_job(hosts=[1], active=1)
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


    def test_metahost_scheduling(self):
        'Basic metahost scheduling'
        self._test_basic_scheduling_helper(True)


    def test_metahost_priorities(self):
        self._test_priorities_helper(True)


    def test_metahost_hosts_ready(self):
        self._test_hosts_ready_helper(True)


    def test_metahost_hosts_idle(self):
        self._test_hosts_idle_helper(True)


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
        self._do_query('UPDATE host_queue_entries SET complete = 1 '
                       'WHERE host_id=1')
        self._dispatcher._schedule_new_jobs()
        self._check_for_extra_schedulings()


    def test_metahosts_obey_ACLs(self):
        "ACL-inaccessible hosts can't get scheduled for metahosts"
        self._do_query('DELETE FROM acl_groups_hosts WHERE host_id=1')
        self._create_job(metahosts=[1])
        self._dispatcher._schedule_new_jobs()
        self._check_for_extra_schedulings()


class PidfileRunMonitorTest(unittest.TestCase):
    results_dir = '/test/path'
    pidfile_path = os.path.join(results_dir, monitor_db.AUTOSERV_PID_FILE)
    pid = 12345
    args = ('nice -n 10 autoserv -P 123-myuser/myhost -p -n '
            '-r ' + results_dir + ' -b -u myuser -l my-job-name '
            '-m myhost /tmp/filejx43Zi -c')
    bad_args = args.replace(results_dir, '/random/results/dir')

    def setUp(self):
        self.god = mock.mock_god()
        self.god.stub_function(monitor_db, 'open')
        self.god.stub_function(os.path, 'exists')
        self.god.stub_function(monitor_db.email_manager,
                               'enqueue_notify_email')
        self.monitor = monitor_db.PidfileRunMonitor(self.results_dir)


    def tearDown(self):
        self.god.unstub_all()


    def set_not_yet_run(self):
        os.path.exists.expect_call(self.pidfile_path).and_return(False)


    def setup_pidfile(self, pidfile_contents):
        os.path.exists.expect_call(self.pidfile_path).and_return(True)
        pidfile = StringIO.StringIO(pidfile_contents)
        monitor_db.open.expect_call(
            self.pidfile_path, 'r').and_return(pidfile)


    def set_running(self):
        self.setup_pidfile(str(self.pid) + '\n')


    def set_complete(self, error_code):
        self.setup_pidfile(str(self.pid) + '\n' +
                           str(error_code) + '\n')


    def _test_read_pidfile_helper(self, expected_pid, expected_exit_status):
        pid, exit_status = self.monitor.read_pidfile()
        self.assertEquals(pid, expected_pid)
        self.assertEquals(exit_status, expected_exit_status)
        self.god.check_playback()


    def test_read_pidfile(self):
        self.set_not_yet_run()
        self._test_read_pidfile_helper(None, None)

        self.set_running()
        self._test_read_pidfile_helper(self.pid, None)

        self.set_complete(123)
        self._test_read_pidfile_helper(self.pid, 123)


    def test_read_pidfile_error(self):
        self.setup_pidfile('asdf')
        self.assertRaises(monitor_db.PidfileException,
                          self.monitor.read_pidfile)
        self.god.check_playback()


    def setup_proc_cmdline(self, args):
        proc_cmdline = args.replace(' ', '\x00')
        proc_file = StringIO.StringIO(proc_cmdline)
        monitor_db.open.expect_call(
            '/proc/%d/cmdline' % self.pid, 'r').and_return(proc_file)


    def setup_find_autoservs(self, process_dict):
        self.god.stub_class_method(monitor_db.Dispatcher,
                                   'find_autoservs')
        monitor_db.Dispatcher.find_autoservs.expect_call().and_return(
            process_dict)


    def _test_get_pidfile_info_helper(self, expected_pid,
                                      expected_exit_status):
        pid, exit_status = self.monitor.get_pidfile_info()
        self.assertEquals(pid, expected_pid)
        self.assertEquals(exit_status, expected_exit_status)
        self.god.check_playback()


    def test_get_pidfile_info(self):
        'normal cases for get_pidfile_info'
        # running
        self.set_running()
        self.setup_proc_cmdline(self.args)
        self._test_get_pidfile_info_helper(self.pid, None)

        # exited during check
        self.set_running()
        monitor_db.open.expect_call(
            '/proc/%d/cmdline' % self.pid, 'r').and_raises(IOError)
        self.set_complete(123) # pidfile gets read again
        self._test_get_pidfile_info_helper(self.pid, 123)

        # completed
        self.set_complete(123)
        self._test_get_pidfile_info_helper(self.pid, 123)


    def test_get_pidfile_info_running_no_proc(self):
        'pidfile shows process running, but no proc exists'
        # running but no proc
        self.set_running()
        monitor_db.open.expect_call(
            '/proc/%d/cmdline' % self.pid, 'r').and_raises(IOError)
        self.set_running()
        monitor_db.email_manager.enqueue_notify_email.expect_call(
            mock.is_string_comparator(), mock.is_string_comparator())
        self._test_get_pidfile_info_helper(self.pid, 1)
        self.assertTrue(self.monitor.lost_process)


    def test_get_pidfile_info_not_yet_run(self):
        "pidfile hasn't been written yet"
        # process not running
        self.set_not_yet_run()
        self.setup_find_autoservs({})
        self._test_get_pidfile_info_helper(None, None)

        # process running
        self.set_not_yet_run()
        self.setup_find_autoservs({self.pid : self.args})
        self._test_get_pidfile_info_helper(None, None)

        # another process running under same pid
        self.set_not_yet_run()
        self.setup_find_autoservs({self.pid : self.bad_args})
        self._test_get_pidfile_info_helper(None, None)


class AgentTest(unittest.TestCase):
    def setUp(self):
        self.god = mock.mock_god()


    def tearDown(self):
        self.god.unstub_all()


    def test_agent(self):
        task1 = self.god.create_mock_class(monitor_db.AgentTask,
                                          'task1')
        task2 = self.god.create_mock_class(monitor_db.AgentTask,
                                          'task2')
        task3 = self.god.create_mock_class(monitor_db.AgentTask,
                                           'task3')

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

        task3.start.expect_call()
        task3.is_done.expect_call().and_return(True)
        task3.is_done.expect_call().and_return(True)
        task3.success = True

        agent = monitor_db.Agent([task1, task2])
        agent.dispatcher = object()
        agent.start()
        while not agent.is_done():
            agent.tick()
        self.god.check_playback()


class AgentTasksTest(unittest.TestCase):
    TEMP_DIR = '/temp/dir'
    HOSTNAME = 'myhost'
    HOST_PROTECTION = host_protections.default

    def setUp(self):
        self.god = mock.mock_god()
        self.god.stub_with(tempfile, 'mkdtemp',
                           mock.mock_function('mkdtemp', self.TEMP_DIR))
        self.god.stub_class_method(monitor_db.RunMonitor, 'run')
        self.god.stub_class_method(monitor_db.RunMonitor, 'exit_code')
        self.host = self.god.create_mock_class(monitor_db.Host, 'host')
        self.host.hostname = self.HOSTNAME
        self.host.protection = self.HOST_PROTECTION
        self.queue_entry = self.god.create_mock_class(
            monitor_db.HostQueueEntry, 'queue_entry')
        self.queue_entry.host = self.host
        self.queue_entry.meta_host = None


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


    def setup_run_monitor(self, exit_status):
        monitor_db.RunMonitor.run.expect_call()
        monitor_db.RunMonitor.exit_code.expect_call()
        monitor_db.RunMonitor.exit_code.expect_call().and_return(
            exit_status)


    def _test_repair_task_helper(self, success):
        self.host.set_status.expect_call('Repairing')
        if success:
            self.setup_run_monitor(0)
            self.host.set_status.expect_call('Ready')
        else:
            self.setup_run_monitor(1)
            self.host.set_status.expect_call('Repair Failed')

        task = monitor_db.RepairTask(self.host)
        self.run_task(task, success)

        expected_protection = host_protections.Protection.get_string(
            host_protections.default)
        self.assertTrue(set(task.monitor.cmd) >=
                        set(['autoserv', '-R', '-m', self.HOSTNAME, '-r',
                             self.TEMP_DIR, '--host-protection',
                             expected_protection]))
        self.god.check_playback()


    def test_repair_task(self):
        self._test_repair_task_helper(True)
        self._test_repair_task_helper(False)


    def test_repair_task_with_queue_entry(self):
        queue_entry = self.god.create_mock_class(
            monitor_db.HostQueueEntry, 'queue_entry')
        self.host.set_status.expect_call('Repairing')
        self.setup_run_monitor(1)
        self.host.set_status.expect_call('Repair Failed')
        queue_entry.handle_host_failure.expect_call()

        task = monitor_db.RepairTask(self.host, queue_entry)
        self.run_task(task, False)
        self.god.check_playback()


    def setup_verify_expects(self, success, use_queue_entry):
        if use_queue_entry:
            self.queue_entry.set_status.expect_call('Verifying')
            self.queue_entry.verify_results_dir.expect_call(
                ).and_return('/verify/results/dir')
            self.queue_entry.clear_results_dir.expect_call(
                '/verify/results/dir')
        self.host.set_status.expect_call('Verifying')
        if success:
            self.setup_run_monitor(0)
            self.host.set_status.expect_call('Ready')
        else:
            self.setup_run_monitor(1)
            if use_queue_entry:
                self.queue_entry.requeue.expect_call()


    def _test_verify_task_with_host_helper(self, success, use_queue_entry):
        self.setup_verify_expects(success, use_queue_entry)

        if use_queue_entry:
            task = monitor_db.VerifyTask(
                queue_entry=self.queue_entry)
        else:
            task = monitor_db.VerifyTask(host=self.host)
        self.run_task(task, success)
        self.assertTrue(set(task.monitor.cmd) >=
                        set(['autoserv', '-v', '-m', self.HOSTNAME, '-r',
                        self.TEMP_DIR]))
        self.god.check_playback()


    def test_verify_task_with_host(self):
        self._test_verify_task_with_host_helper(True, False)
        self._test_verify_task_with_host_helper(False, False)


    def test_verify_task_with_queue_entry(self):
        self._test_verify_task_with_host_helper(True, True)
        self._test_verify_task_with_host_helper(False, True)


    def test_verify_synchronous_task(self):
        job = self.god.create_mock_class(monitor_db.Job, 'job')

        self.setup_verify_expects(True, True)
        job.num_complete.expect_call().and_return(0)
        self.queue_entry.set_status.expect_call('Pending')
        job.is_ready.expect_call().and_return(True)
        job.run.expect_call(self.queue_entry)
        self.queue_entry.job = job

        task = monitor_db.VerifySynchronousTask(self.queue_entry)
        task.agent = Dummy()
        task.agent.dispatcher = Dummy()
        self.god.stub_with(task.agent.dispatcher, 'add_agent',
                           mock.mock_function('add_agent'))
        self.run_task(task, True)
        self.god.check_playback()


if __name__ == '__main__':
    unittest.main()
