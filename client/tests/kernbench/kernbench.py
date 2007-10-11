import test, pickle
from autotest_utils import *
import re

class kernbench(test.test):
	version = 1

	def setup(self, build_dir = None):
		if not build_dir:
			build_dir = self.srcdir
		#
		# If we have a local copy of the 2.6.14 tarball use that
		# else let the kernel object use the defined mirrors
		# to obtain it.
		#
		# http://kernel.org/pub/linux/kernel/v2.6/linux-2.6.14.tar.bz2
		#
		# On ia64, we default to 2.6.20, as it can't compile 2.6.14.

		if get_current_kernel_arch() == 'ia64':
			default_ver = '2.6.20'
		else:
			default_ver = '2.6.14'
		tarball = None
		for dir in (self.bindir, '/usr/local/src'):
			tar = 'linux-%s.tar.bz2' % default_ver
			path = os.path.join(dir, tar)
			if os.path.exists(path):
				tarball = path
				break
		if not tarball:
			tarball = default_ver

		# Do the extraction of the kernel tree
		kernel = self.job.kernel(tarball, self.tmpdir, build_dir)
		kernel._config(defconfig=True)


	def execute(self, iterations = 1, threads = 2*count_cpus(), dir = None):
		if dir:
			build_dir = dir
			self.setup(build_dir)
		else:
			build_dir = self.srcdir

		kernel = self.job.kernel(build_dir, self.tmpdir, build_dir,
								leave = True)
		print "kernbench x %d: %d threads" % (iterations, threads)

		logfile = os.path.join(self.debugdir, 'build_log')

		print "Warmup run ..."
		kernel.build_timed(threads, output = logfile)      # warmup run

		profilers = self.job.profilers
                if not profilers.only():
		        for i in range(iterations):
				print "Performance run, iteration %d ..." % i
			        timefile = os.path.join(self.resultsdir, 
								'time.%d' % i)
			        kernel.build_timed(threads, timefile,
							output = logfile)

		# Do a profiling run if necessary
		if profilers.present():
			profilers.start(self)
			print "Profiling run ..."
			timefile = os.path.join(self.resultsdir, 'time.profile')
			kernel.build_timed(threads, timefile, output = logfile)
			profilers.stop(self)
			profilers.report(self)

		kernel._clean()		# Don't leave litter lying around
		os.chdir(self.resultsdir)
		system("grep -h elapsed time.* > time")

		self.__format_results(open('time').read())


	def __format_results(self, results):
		out = open('keyval', 'w')
		for result in extract_all_time_results(results):
			print >> out, "user=%s\nsystem=%s\nelapsed=%s\n" % result
		out.close()
