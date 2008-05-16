import test,time,os,signal
from autotest_utils import *

class tbench(test.test):
	version = 2 

	# http://samba.org/ftp/tridge/dbench/dbench-3.04.tar.gz
	def setup(self, tarball = 'dbench-3.04.tar.gz'):
		tarball = unmap_url(self.bindir, tarball, self.tmpdir)
		extract_tarball_to_dir(tarball, self.srcdir)
		os.chdir(self.srcdir)

		system('./configure')
		system('make')

	def execute(self, iterations = 1, nprocs = None, args = ''):
		# only supports combined server+client model at the moment
		# should support separate I suppose, but nobody uses it
		if not nprocs:
			nprocs = self.job.cpu_count()
		args += ' %s' % nprocs
		results = []
		profilers = self.job.profilers
		if not profilers.only():
			for i in range(iterations):
				results.append(self.run_tbench(args))

		# Do a profiling run if necessary
		if profilers.present():
			profilers.start(self)
			results.append(self.run_tbench(args))
			profilers.stop(self)
			profilers.report(self)

		self.__format_results("\n".join(results))


	def run_tbench(self, args):
		pid = os.fork()
		if pid:				# parent
			time.sleep(1)
			client = self.srcdir + '/client.txt'
			args = '-c ' + client + ' ' + '%s' % args
			cmd = os.path.join(self.srcdir, "tbench") + " " + args
			results = system_output(cmd, retain_output=True)
			os.kill(pid, signal.SIGTERM)    # clean up the server
		else:				# child
			server = self.srcdir + '/tbench_srv'
			os.execlp(server, server)
		return results


	def __format_results(self, results):
		out = open(self.resultsdir + '/keyval', 'w')
		pattern = re.compile(r"Throughput (.*?) MB/sec (.*?) procs")
		for result in pattern.findall(results):
			print >> out, "throughput=%s\nprocs=%s\n" % result
		out.close()
