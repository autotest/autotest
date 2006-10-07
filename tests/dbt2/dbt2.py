import test
from autotest_utils import *

# Dbt-2 is a fair-use implementation of the TPC-C benchmark.  The test is 
# currently hardcoded to use PostgreSQL but the kit also supports MySQL.

class dbt2(test.test):
	version = 2

	# http://osdn.dl.sourceforge.net/sourceforge/osdldbt/dbt2-0.39.tar.gz
	def setup(self, tarball = 'dbt2-0.39.tar.bz2'):
		tarball = unmap_url(self.bindir, tarball, self.tmpdir)
		extract_tarball_to_dir(tarball, self.srcdir)
		self.job.setup_dep(['pgsql', 'pgpool', 'mysql'])

		#
		# Extract one copy of the kit for MySQL.
		#
		system('cp -pR ' + self.srcdir + ' ' + self.srcdir + '.mysql')
		os.chdir(self.srcdir + '.mysql')
		system('./configure --with-mysql=%s/deps/mysql/mysql' \
				% self.autodir)
		system('make')

		#
		# Extract one copy of the kit for PostgreSQL.
		#
		system('cp -pR ' + self.srcdir + ' ' + self.srcdir + '.pgsql')
		os.chdir(self.srcdir + '.pgsql')
		system('./configure --with-postgresql=%s/deps/pgsql/pgsql' \
				% self.autodir)
		system('make')

		# Create symlinks to autotest's results directory from dbt-2's
		# preferred results directory to self.resultsdir
		system('ln -s %s %s' % (self.resultsdir, \
				self.srcdir + '.mysql/scripts/output'))
		system('ln -s %s %s' % (self.resultsdir, \
				self.srcdir + '.pgsql/scripts/output'))

	def execute(self, db_type, args = ''):
		logfile = self.resultsdir + '/dbt2.log'

		if (db_type == "mysql"):
			self.execute_mysql(args)
		elif (db_type == "pgpool"):
			self.execute_pgpool(args)
		elif (db_type == "pgsql"):
			self.execute_pgsql(args)

	def execute_mysql(self, args = ''):
		args = args
		system(self.srcdir + '.mysql/scripts/mysql/build_db.sh -g -w 1')
		system(self.srcdir + '.mysql/scripts/run_workload.sh ' + args)

 	def execute_pgpool(self, args = ''):
 		system('%s/deps/pgpool/pgpool/bin/pgpool -f %s/../pgpool.conf' \
 				% (self.autodir, self.srcdir))
 		self.execute_pgsql(args)
 		system('%s/deps/pgpool/pgpool/bin/pgpool stop' % self.autodir)


	def execute_pgsql(self, args = ''):
		system(self.srcdir + '.pgsql/scripts/pgsql/build_db.sh -g -w 1')
		system(self.srcdir + '.pgsql/scripts/run_workload.sh ' + args)
		#
		# Clean up by dropping the database after the test.
		#
		system(self.srcdir + '.pgsql/scripts/pgsql/start_db.sh')
		system(self.srcdir + '.pgsql/scripts/pgsql/drop_db.sh')
		system(self.srcdir + '.pgsql/scripts/pgsql/stop_db.sh')
