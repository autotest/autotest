import test
from autotest_utils import *

class netperf2(test.test):
	version = 1

	# ftp://ftp.netperf.org/netperf/netperf-2.4.1.tar.gz
	def setup(self, tarball = 'netperf-2.4.1.tar.gz'):
		tarball = unmap_url(self.bindir, tarball, self.tmpdir)
		extract_tarball_to_dir(tarball, self.srcdir)
		os.chdir(self.srcdir)

		system('./configure')
		system('make')
		
	def execute(self, script = 'snapshot_script', args = ''):
		self.server_path = os.path.join(self.srcdir, 'src/netserver')
		self.client_path = os.path.join(self.srcdir, 'src/netperf')

		os.environ['NETPERF_CMD'] = client_path
		self.server_start()
		self.client(script)
		self.server_stop()

	def server_start(self):
		# we should record the pid we forked off
		system(server_path)

	def server_stop(self):
		# this should really just kill the pid I forked, but ...
		system('killall netserver')

	def client(self, script, server_host = 'localhost', args = 'CPU'):
		# run some client stuff
		stdout_path = os.path.join(self.resultsdir, script + '.stdout')
		stderr_path = os.path.join(self.resultsdir, script + '.stderr')

		self.job.stdout.tee_redirect(stdout_path)
		self.job.stderr.tee_redirect(stderr_path)
		system(os.path.join(self.srcdir, 'doc/examples', script) + args)
		self.job.stdout.restore()
		self.job.stderr.restore()
