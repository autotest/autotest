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

		
	def execute(self, server_ip, client_ip, role, 
					script='snapshot_script', args=''):
		server_tag = server_ip + '#netperf-server'
		client_tag = client_ip + '#netperf-client'
		all = [server_tag, client_tag]
		job = self.job
		if (role == 'server'):
			self.server_start()
			try:
				job.barrier(server_tag, 'start',
							30).rendevous(*all)
				job.barrier(server_tag, 'stop',
							3600).rendevous(*all)
			finally:
				self.server_stop()
		elif (role == 'client'):
			os.environ['NETPERF_CMD'] = self.client_path
			job.barrier(client_tag, 'start', 30).rendevous(*all)
			self.client(script, server_ip, args)
			job.barrier(client_tag, 'stop',  30).rendevous(*all)
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


	def client(self, script, server_ip, args = 'CPU'):
		# run some client stuff
		stdout_path = os.path.join(self.resultsdir, script + '.stdout')
		stderr_path = os.path.join(self.resultsdir, script + '.stderr')
		self.job.stdout.tee_redirect(stdout_path)
		self.job.stderr.tee_redirect(stderr_path)

		script_path = os.path.join(self.srcdir, 'doc/examples', script)
		system('%s %s %s' % (script_path, server_ip, args))

		self.job.stdout.restore()
		self.job.stderr.restore()
