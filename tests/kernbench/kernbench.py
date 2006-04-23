import test
from autotest_utils import *

class kernbench(test.test):
	def setup(self, kernelver = '/usr/local/src/linux-2.6.14.tar.bz2',
  		   config = os.environ['AUTODIR'] + "/tests/kernbench/config"):

		self.top_dir = self.job.tmpdir+'/kernbench'
		kernel = self.job.kernel(self.top_dir, kernelver)
		kernel.config(config)


	def execute(self, iterations = 1, threads = 2 * count_cpus()):
		print "kernbench x %d: %d threads" % (iterations, threads)

		kernel.build_timed(threads)         # warmup run
		for i in range(1, iterations+1):
			kernel.build_timed(threads, '../log/time.%d' % i)

		os.chdir(top_dir + '/log')
		system("grep elapsed time.* > time")
