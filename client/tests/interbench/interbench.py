import test
from autotest_utils import *

class interbench(test.test):
	version = 1

	# http://www.kernel.org/pub/linux/kernel/people/ck/apps/interbench/interbench-0.30.tar.bz2
	def setup(self, tarball = 'interbench-0.30.tar.bz2'):
		tarball = unmap_url(self.bindir, tarball, self.tmpdir)
		extract_tarball_to_dir(tarball, self.srcdir)
		os.chdir(self.srcdir)

		system('make')
		
	def execute(self, iterations = 1, args = ''):
		os.chdir(self.tmpdir)
		args += " -c"

		for i in range(1, iterations+1):
			system("%s/interbench -m 'run #%s' %s" % \
				(self.srcdir, i, args))

		# Do a profiling run if necessary
		profilers = self.job.profilers
		if profilers.present():
			profilers.start(self)
			system("%s/interbench -m 'profile run' %s" % \
				(self.srcdir, args))
			profilers.stop(self)
			profilers.report(self)
