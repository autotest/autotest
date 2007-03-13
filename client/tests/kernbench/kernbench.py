import test, pickle
from autotest_utils import *

class kernbench(test.test):
	version = 1

	def setup(self):
		#
		# If we have a local copy of the 2.6.14 tarball use that
		# else let the kernel object use the defined mirrors
		# to obtain it.
		#
		# http://kernel.org/pub/linux/kernel/v2.6/linux-2.6.14.tar.bz2
		#
		tarball = None
		for dir in (self.bindir, '/usr/local/src'):
			path = os.path.join(dir, 'linux-2.6.14.tar.bz2')
			if os.path.exists(path):
				tarball = path
				break
		if not tarball:
			tarball = '2.6.14'
			
		kernel = self.job.kernel(tarball, self.tmpdir, self.srcdir)
		kernel.config(defconfig=True)
		# have to save this off, as we might use it in another run
		kernel.pickle_dump(self.srcdir + '/.pickle')


	def execute(self, iterations = 1, threads = 2 * count_cpus()):
		kernel = pickle.load(open(self.srcdir + '/.pickle', 'r'))
		kernel.job = self.job
		print "kernbench x %d: %d threads" % (iterations, threads)

		kernel.build_timed(threads)         # warmup run
		for i in range(iterations):
			logfile = self.resultsdir+'/time.%d' % i
			kernel.build_timed(threads, logfile)

		# Do a profiling run if necessary
		profilers = self.job.profilers
		if profilers.present():
			profilers.start(self)
			logfile = self.resultsdir+'/time.profile'
			kernel.build_timed(threads, logfile)
			profilers.stop(self)
			profilers.report(self)

		kernel.clean()		# Don't leave litter lying around
		os.chdir(self.resultsdir)
		system("grep -h elapsed time.* > time")
