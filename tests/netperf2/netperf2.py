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


	def initialize(self):
		self.server_path = os.path.join(self.srcdir, 'src/netserver')
		self.client_path = os.path.join(self.srcdir, 'src/netperf')

		
	def execute(self, role='client', script='snapshot_script', args=''):
		all = ['127.0.0.1#netperf-server', '127.0.0.1#netperf-client']
		job = self.job
		if (role == 'server'):
			hostid = '127.0.0.1#netperf-server'
			self.server_start()
			job.barrier(hostid, 'start', 30).rendevous(*all)
			job.barrier(hostid, 'stop',  3600).rendevous(*all)
			self.server_stop()
		elif (role == 'client'):
			hostid = '127.0.0.1#netperf-client'
			os.environ['NETPERF_CMD'] = self.client_path
			job.barrier(hostid, 'start', 30).rendevous(*all)
			self.client(script)
			job.barrier(hostid, 'stop',  30).rendevous(*all)
		else:
			raise UnhandledError('invalid role specified')


	def server_start(self):
		# we should really record the pid we forked off, but there
		# was no obvious way to run the daemon in the foreground.
		# Hacked it for now
		system('killall netserver', ignorestatus=1)
		system(self.server_path)


	def server_stop(self):
		# this should really just kill the pid I forked, but ...
		system('killall netserver')


	def client(self, script, server_host = 'localhost', args = 'CPU'):
		# run some client stuff
		stdout_path = os.path.join(self.resultsdir, script + '.stdout')
		stderr_path = os.path.join(self.resultsdir, script + '.stderr')

		self.job.stdout.tee_redirect(stdout_path)
		self.job.stderr.tee_redirect(stderr_path)
		system(os.path.join(self.srcdir, 'doc/examples', script) \
								+ ' ' + args)
		self.job.stdout.restore()
		self.job.stderr.restore()
