#!/usr/bin/python

import unittest, time, subprocess
import MySQLdb
import common
from autotest_lib.client.common_lib import global_config
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
			     'Job %d not scheduled on host %d as expected' %
			     (job_id, host_id))
		self._jobs_scheduled.remove(record)


	def _check_for_extra_schedulings(self):
		if len(self._jobs_scheduled) != 0:
			self.fail('Extra jobs scheduled: ' +
				  str(self._jobs_scheduled))


	def _create_job(self, hosts=[], metahosts=[], priority=0, active=0):
		self._do_query('INSERT INTO jobs (name, priority) VALUES '
			       '("test", %d)' % priority)
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


	def test_priorities(self):
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
		self._dispatcher._schedule_new_jobs()
		self._assert_job_scheduled_on(1, 1)
		self._check_for_extra_schedulings()


	def test_metahosts_obey_ACLs(self):
		"ACL-inaccessible hosts can't get scheduled for metahosts"
		self._do_query('DELETE FROM acl_groups_hosts WHERE host_id=1')
		self._create_job(metahosts=[1])
		self._do_query('INSERT INTO ineligible_host_queues '
			       '(job_id, host_id) VALUES (1, 1)')
		self._dispatcher._schedule_new_jobs()
		self._check_for_extra_schedulings()


if __name__ == '__main__':
	unittest.main()
