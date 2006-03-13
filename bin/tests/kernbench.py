import test
from autotest_utils import *

class kernbench(test):

	def setup(self,
			iterations = 1,
			threads = 2 * count_cpus(),
			kernelver = autodir + '/src/linux-2.6.14.tar.bz2',
			config = autodir + "/bin/tests/kernbench/config"):
		
		print "kernbench -j %d -i %d -c %s -k %s" % (threads, iterations, config, kernelver)

		self.iterations = iterations
		self.threads = threads
		self.kernelver = kernelver
		self.config = config

		top_dir = job.tmpdir+'/kernbench'
		kernel = job.kernel(top_dir, kernelver)
		kernel.config([config])


	def execute(self):
		testkernel.build_timed(threads)         # warmup run
		for i in range(1, iterations+1):
			testkernel.build_timed(threads, '../log/time.%d' % i)

		os.chdir(top_dir + '/log')
		os.system("grep elapsed time.* > time")
