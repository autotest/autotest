#!/usr/bin/python2.4

import os, sys, re, subprocess, tempfile
import MySQLdb, MySQLdb.constants.ER
from optparse import OptionParser
from common import global_config

MIGRATE_TABLE = 'migrate_info'
DEFAULT_MIGRATIONS_DIR = 'migrations'

class Migration(object):
	version = None
	module = None

	def __init__(self, filename):
		self.version = int(filename[:3])
		self.module = filename[:-3]


class MigrationManager(object):
	connection = None
	cursor = None
	migrations_dir = None

	def __init__(self, database, migrations_dir=None, db_host=None, db_name=None,
		     username=None, password=None):
		self.database = database
		if migrations_dir is None:
			migrations_dir = os.path.abspath(DEFAULT_MIGRATIONS_DIR)
		self.migrations_dir = migrations_dir
		sys.path.append(migrations_dir)
		assert os.path.exists(migrations_dir)

		self.db_host = db_host
		self.db_name = db_name
		self.username = username
		self.password = password


	def read_db_info(self):
		# grab the config file and parse for info
		c = global_config.global_config
		print "database = %s\n" % (self.database)
		self.db_host = c.get_config_value(self.database, "host")
		self.db_name = c.get_config_value(self.database, "database")
		self.username = c.get_config_value(self.database, "user")
		self.password = c.get_config_value(self.database, "password")


	def connect(self, host, db_name, username, password):
		return MySQLdb.connect(host=host, db=db_name, user=username,
				       passwd=password)


	def open_connection(self):
		self.connection = self.connect(self.db_host, self.db_name,
					       self.username, self.password)
		self.cursor = self.connection.cursor()


	def close_connection(self):
		self.connection.close()


	def execute(self, query, *parameters):
		#print 'SQL:', query % parameters
		return self.cursor.execute(query, parameters)


	def execute_script(self, script):
		sql_statements = [statement.strip() for statement
				  in script.split(';')]
		for statement in sql_statements:
			if statement:
				self.execute(statement)


	def check_migrate_table_exists(self):
		try:
			self.execute("SELECT * FROM %s" % MIGRATE_TABLE)
			return True
		except MySQLdb.ProgrammingError, exc:
			error_code, _ = exc.args
			if error_code == MySQLdb.constants.ER.NO_SUCH_TABLE:
				return False
			raise


	def create_migrate_table(self):
		self.execute("CREATE TABLE %s (`version` integer)" %
			     MIGRATE_TABLE)
		self.execute("INSERT INTO %s VALUES (0)" % MIGRATE_TABLE)
		assert self.cursor.rowcount == 1


	def set_db_version(self, version):
		assert isinstance(version, int)
		self.execute("UPDATE %s SET version=%%s" % MIGRATE_TABLE,
			     version)
		assert self.cursor.rowcount == 1


	def get_db_version(self):
		if not self.check_migrate_table_exists():
			return 0
		self.execute("SELECT * FROM %s" % MIGRATE_TABLE)
		rows = self.cursor.fetchall()
		assert len(rows) == 1 and len(rows[0]) == 1
		return rows[0][0]


	def get_migrations(self, minimum_version=None):
		migrate_files = [filename for filename
				 in os.listdir(self.migrations_dir)
				 if re.match(r'^\d\d\d_.*\.py$', filename)]
		migrate_files.sort()
		migrations = [Migration(filename) for filename in migrate_files]
		if minimum_version is not None:
			migrations = [migration for migration in migrations
				      if migration.version >= minimum_version]
		return migrations


	def do_migration(self, migration):
		assert self.get_db_version() == migration.version - 1
		print 'Applying migration', migration.module
		module_object = __import__(migration.module,
					   globals(), locals(), [])
		up_method = getattr(module_object, 'migrate_up', None)
		assert up_method is not None
		up_method(self)
		self.set_db_version(migration.version)


	def migrate_to_version(self, version):
		current_version = self.get_db_version()
		# no support for migrating down right now
		assert current_version <= version

		migrations = self.get_migrations(current_version + 1)
		for migration in migrations:
			self.do_migration(migration)

		assert self.get_db_version() == version
		print 'At version', version


	def migrate_to_latest(self):
		migrations = self.get_migrations()
		latest_version = migrations[-1].version
		self.migrate_to_version(latest_version)


	def initialize_test_db(self):
		self.read_db_info()
		test_db_name = 'test_' + self.db_name
		# first, connect to no DB so we can create a test DB
		self.db_name = ''
		self.open_connection()
		print 'Creating test DB', test_db_name
		self.execute('CREATE DATABASE ' + test_db_name)
		self.close_connection()
		# now connect to the test DB
		self.db_name = test_db_name
		self.open_connection()


	def remove_test_db(self):
		print 'Removing test DB'
		self.execute('DROP DATABASE ' + self.db_name)


	def get_mysql_args(self):
		return ('-u %(user)s -p%(password)s -h %(host)s %(db)s' % {
		    'user' : self.username,
		    'password' : self.password,
		    'host' : self.db_host,
		    'db' : self.db_name})


	def do_sync_db(self):
		self.read_db_info()
		self.open_connection()
		print 'Migration starting for database', self.db_name
		self.migrate_to_latest()
		print 'Migration complete'


	def test_sync_db(self):
		"""\
		Create a fresh DB and run all migrations on it.
		"""
		self.initialize_test_db()
		try:
			print 'Starting migration test on DB', self.db_name
			self.migrate_to_latest()
			# show schema to the user
			os.system('mysqldump %s --no-data=true '
				  '--add-drop-table=false' %
				  self.get_mysql_args())
		finally:
			self.remove_test_db()
		print 'Test finished successfully'


	def simulate_sync_db(self):
		"""\
		Create a fresh DB, copy the existing DB to it, and then
		try to synchronize it.
		"""
		# get existing data
		self.read_db_info()
		print 'Dumping existing data'
		dump_fd, dump_file = tempfile.mkstemp('.migrate_dump')
		os.close(dump_fd)
		os.system('mysqldump %s >%s' %
			  (self.get_mysql_args(), dump_file))
		# fill in test DB
		self.initialize_test_db()
		print 'Filling in test DB'
		os.system('mysql %s <%s' % (self.get_mysql_args(), dump_file))
		os.remove(dump_file)
		try:
			print 'Starting migration test on DB', self.db_name
			self.migrate_to_latest()
		finally:
			self.remove_test_db()
		print 'Test finished successfully'


USAGE = 'must specify one of [sync|test|simulate|safesync]'


def main():
	parser = OptionParser()
	parser.add_option("-d", "--database",
			  help="which database to act on",
			  dest="database")
	parser.add_option("-a", "--action", help="what action to perform",
			  dest="action")
	(options, args) = parser.parse_args()
	manager = MigrationManager(options.database)
	
	if len(args) > 0:
		if args[0] == 'sync':
			manager.do_sync_db()
		elif args[0] == 'test':
			manager.test_sync_db()
		elif args[0] == 'simulate':
			manager.simulate_sync_db()
		elif args[0] == 'safesync':
			print 'Simluating migration'
			manager.simulate_sync_db()
			print 'Performing real migration'
			manager.do_sync_db()
		else:
			print USAGE
		return
	
	print USAGE


if __name__ == '__main__':
	main()
