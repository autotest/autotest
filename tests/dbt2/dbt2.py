import test
from autotest_utils import *

# Dbt-2 is a fair-use implementation of the TPC-C benchmark.  The test is 
# currently hardcoded to use PostgreSQL but the kit also supports MySQL.

class dbt2(test.test):
	version = 1

	# http://osdn.dl.sourceforge.net/sourceforge/osdldbt/dbt2-0.38.tar.gz
	def setup(self, tarball = 'dbt2-0.38.tar.gz'):
		tarball = unmap_url(self.bindir, tarball, self.tmpdir)
		extract_tarball_to_dir(tarball, self.srcdir)
		self.job.setup_dep(['pgsql'])

		# Create symlink to autotest's results directory from dbt-2's
		# preferred results directory to self.resultsdir
		system('ln -s %s %s' % (self.resultsdir, \
				os.path.join(self.srcdir,'/scripts/output')))

	def execute(self, args = ''):
		logfile = self.resultsdir + '/dbt2.log'

		os.chdir(self.srcdir)
		system('./configure --with-postgresql=/usr/local/pgsql-autotest')
		system('make')
		os.chdir(self.srcdir + '/scripts')
		system('pgsql/build_db.sh -g')
		system(self.srcdir + '/scripts/run_workload.sh ' + args)
		#
		# Clean up by dropping the database after the test.
		#
		system('pgsql/start_db.sh')
		system('pgsql/drop_db.sh')
		system('pgsql/stop_db.sh')
