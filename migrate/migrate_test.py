#!/usr/bin/python2.4

import unittest
import MySQLdb
import migrate
from common import global_config

# Which section of the global config to pull info from.  We won't actually use
# that DB, we'll use the corresponding test DB (test_<db name>).
CONFIG_DB = 'AUTOTEST_WEB'

NUM_MIGRATIONS = 3

class DummyMigration(object):
	"""\
	Dummy migration class that records all migrations done in a class
	varaible.
	"""

	migrations_done = []

	def __init__(self, version):
		self.version = version
		self.name = '%03d_test' % version


	@classmethod
	def get_migrations_done(cls):
		return cls.migrations_done


	@classmethod
	def clear_migrations_done(cls):
		cls.migrations_done = []


	@classmethod
	def do_migration(cls, version, direction):
		cls.migrations_done.append((version, direction))


	def migrate_up(self, manager):
		self.do_migration(self.version, 'up')
		if self.version == 1:
			manager.create_migrate_table()


	def migrate_down(self, manager):
		self.do_migration(self.version, 'down')


MIGRATIONS = [DummyMigration(n) for n in xrange(1, NUM_MIGRATIONS + 1)]


class TestableMigrationManager(migrate.MigrationManager):
	def __init__(self, database, migrations_dir=None):
		self.database = database
		self.migrations_dir = migrations_dir
		self.db_host = None
		self.db_name = None
		self.username = None
		self.password = None


	def read_db_info(self):
		migrate.MigrationManager.read_db_info(self)
		self.db_name = 'test_' + self.db_name


	def get_migrations(self, minimum_version=None, maximum_version=None):
		minimum_version = minimum_version or 1
		maximum_version = maximum_version or len(MIGRATIONS)
		return MIGRATIONS[minimum_version-1:maximum_version]


class MigrateManagerTest(unittest.TestCase):
	config = global_config.global_config
	host = config.get_config_value(CONFIG_DB, 'host')
	db_name = 'test_' + config.get_config_value(CONFIG_DB, 'database')
	user = config.get_config_value(CONFIG_DB, 'user')
	password = config.get_config_value(CONFIG_DB, 'password')

	def do_sql(self, sql):
		self.con = MySQLdb.connect(host=self.host, user=self.user,
					   passwd=self.password)
		self.con.autocommit(True)
		self.cur = self.con.cursor()
		try:
			self.cur.execute(sql)
		finally:
			self.con.close()


	def remove_db(self):
		self.do_sql('DROP DATABASE ' + self.db_name)


	def setUp(self):
		self.do_sql('CREATE DATABASE ' + self.db_name)
		try:
			self.manager = TestableMigrationManager(CONFIG_DB)
		except MySQLdb.OperationalError:
			self.remove_db()
			raise
		DummyMigration.clear_migrations_done()


	def tearDown(self):
		self.remove_db()


	def test_sync(self):
		self.manager.do_sync_db()
		self.assertEquals(self.manager.get_db_version(), NUM_MIGRATIONS)
		self.assertEquals(DummyMigration.get_migrations_done(),
				  [(1, 'up'), (2, 'up'), (3, 'up')])

		DummyMigration.clear_migrations_done()
		self.manager.do_sync_db(0)
		self.assertEquals(self.manager.get_db_version(), 0)
		self.assertEquals(DummyMigration.get_migrations_done(),
				  [(3, 'down'), (2, 'down'), (1, 'down')])


	def test_sync_one_by_one(self):
		for version in xrange(1, NUM_MIGRATIONS + 1):
			self.manager.do_sync_db(version)
			self.assertEquals(self.manager.get_db_version(),
					  version)
			self.assertEquals(
			    DummyMigration.get_migrations_done()[-1],
			    (version, 'up'))

		for version in xrange(NUM_MIGRATIONS - 1, -1, -1):
			self.manager.do_sync_db(version)
			self.assertEquals(self.manager.get_db_version(),
					  version)
			self.assertEquals(
			    DummyMigration.get_migrations_done()[-1],
			    (version + 1, 'down'))


	def test_null_sync(self):
		self.manager.do_sync_db()
		DummyMigration.clear_migrations_done()
		self.manager.do_sync_db()
		self.assertEquals(DummyMigration.get_migrations_done(), [])


if __name__ == '__main__':
	unittest.main()
