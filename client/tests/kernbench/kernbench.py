import test, pickle
from autotest_utils import *
import re


def to_seconds(time_string):
	elts = time_string.split(':')
	if len(elts) == 1:
		return time_string
	return str(int(elts[0]) * 3600 + float(elts[1]))


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
			
		kernel = self.job.kernel(tarball, self.tmpdir, self.srcdir)
		kernel.config(defconfig=True)
		# have to save this off, as we might use it in another run
		kernel.pickle_dump(self.srcdir + '/.pickle')


	def execute(self, iterations = 1, threads = 2 * count_cpus()):
		kernel = pickle.load(open(self.srcdir + '/.pickle', 'r'))
		kernel.job = self.job
		print "kernbench x %d: %d threads" % (iterations, threads)

		kernel.build_timed(threads)         # warmup run
		profilers = self.job.profilers
                if not profilers.only():
		        for i in range(iterations):
			        logfile = self.resultsdir+'/time.%d' % i
			        kernel.build_timed(threads, logfile)

		# Do a profiling run if necessary
		if profilers.present():
			profilers.start(self)
			logfile = self.resultsdir+'/time.profile'
			kernel.build_timed(threads, logfile)
			profilers.stop(self)
			profilers.report(self)

		kernel.clean()		# Don't leave litter lying around
		os.chdir(self.resultsdir)
		system("grep -h elapsed time.* > time")

		self.__format_results(open('time').read())


	def __format_results(self, results):
		out = open('keyval', 'w')
		pattern = re.compile(r"(.*?)user (.*?)system (.*?)elapsed")
		for result in pattern.findall(results):
			result = tuple([to_seconds(elt) for elt in result])
			print >> out, "user=%s\nsystem=%s\nelapsed=%s\n" % result
		out.close()
