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
		self.job.setup_dep(['pgsql', 'mysql'])

		# Create symlink to autotest's results directory from dbt-2's
		# preferred results directory to self.resultsdir
		system('ln -s %s %s' % (self.resultsdir, \
				self.srcdir + '/scripts/output'))

	def execute(self, args = ''):
		logfile = self.resultsdir + '/dbt2.log'

		os.chdir(self.srcdir)
		system('make clean')
		system('./configure --with-mysql=%s/deps/mysql/mysql' \
				% self.autodir)
		system('make')
		os.chdir(self.srcdir + '/scripts')
		system('mysql/build_db.sh -g -w 1')
		args = args + ' -u root'
		system(self.srcdir + '/scripts/run_workload.sh ' + args)

		os.chdir(self.srcdir)
		system('make clean')
		system('./configure --with-postgresql=%s/deps/pgsql/pgsql' \
				% self.autodir)
		system('make')
		os.chdir(self.srcdir + '/scripts')
		system('pgsql/build_db.sh -g -w 1')
		system(self.srcdir + '/scripts/run_workload.sh ' + args)
		#
		# Clean up by dropping the database after the test.
		#
		system('pgsql/start_db.sh')
		system('pgsql/drop_db.sh')
		system('pgsql/stop_db.sh')
