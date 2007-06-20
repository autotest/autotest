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


	def execute(self, iterations = 1, dir = None, nprocs = count_cpus(), args = ''):
		for i in range(iterations):
			args = args + ' -c '+self.srcdir+'/client.txt'
			if dir:
				args += ' -D ' + dir
			args += ' %s' % nprocs
			system(self.srcdir + '/dbench ' + args)

		# Do a profiling run if necessary
		profilers = self.job.profilers
		if profilers.present():
			profilers.start(self)
			system(self.srcdir + '/dbench ' + args)
			profilers.stop(self)
			profilers.report(self)

		self.__format_results(open(self.debugdir + '/stdout').read())


	def __format_results(self, results):
		out = open(self.resultsdir + '/keyval', 'w')
		pattern = re.compile(r"Throughput (.*?) MB/sec (.*?) procs")
		for result in pattern.findall(results):
			print >> out, "throughput=%s\nprocs=%s\n" % result
		out.close()
