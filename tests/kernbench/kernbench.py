import test, pickle
from autotest_utils import *

class kernbench(test.test):
	version = 1

	def setup(self):
		tarball = '/usr/local/src/linux-2.6.14.tar.bz2'
		config = self.bindir + "/config"
		kernel = self.job.kernel(self.srcdir, tarball)
		kernel.config(config)
		# have to save this off, as we might use it in another run
		kernel.pickle_dump(self.srcdir + '/.pickle')


	def execute(self, iterations = 1, threads = 2 * count_cpus()):
		kernel = pickle.load(open(self.srcdir + '/.pickle', 'r'))
		print "kernbench x %d: %d threads" % (iterations, threads)

		kernel.build_timed(threads)         # warmup run
		for i in range(1, iterations+1):
			logfile = self.resultsdir+'/time.%d' % i
			kernel.build_timed(threads, logfile)

		kernel.clean()		# Don't leave litter lying around
		os.chdir(self.resultsdir)
		system("grep elapsed time.* > time")
