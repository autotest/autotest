import test
from autotest_utils import *

class dbench(test.test):
	version = 1

	# http://samba.org/ftp/tridge/dbench/dbench-3.04.tar.gz
	def setup(self, tarball = 'dbench-3.04.tar.gz'):
		tarball = unmap_url(self.bindir, tarball, self.tmpdir)
		extract_tarball_to_dir(tarball, self.srcdir)
		os.chdir(self.srcdir)

		system('./configure')
		system('make')


	def execute(self, iterations = 1, dir = None, nprocs = None, args = ''):
		if not nprocs:
			nprocs = self.job.cpu_count()
		profilers = self.job.profilers
		args = args + ' -c '+self.srcdir+'/client.txt'
		if dir:
			args += ' -D ' + dir
		args += ' %s' % nprocs
		cmd = self.srcdir + '/dbench ' + args
		results = ''
		if not profilers.only():
			for i in range(iterations):
				results += system_output(cmd) + '\n'

		# Do a profiling run if necessary
		if profilers.present():
			profilers.start(self)
			results += system_output(cmd) + '\n'
			profilers.stop(self)
			profilers.report(self)

		print results
		self.__format_results(results)


	def __format_results(self, results):
		out = open(self.resultsdir + '/keyval', 'w')
		pattern = re.compile(r"Throughput (.*?) MB/sec (.*?) procs")
		for result in pattern.findall(results):
			print >> out, "throughput=%s\nprocs=%s\n" % result
		out.close()
