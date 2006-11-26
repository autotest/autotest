import test
from autotest_utils import *

class unixbench(test.test):
	version = 1

	# http://www.tux.org/pub/tux/niemi/unixbench/unixbench-4.1.0.tgz
	def setup(self, tarball = 'unixbench-4.1.0.tar.bz2'):
		tarball = unmap_url(self.bindir, tarball, self.tmpdir)
		extract_tarball_to_dir(tarball, self.srcdir)
		os.chdir(self.srcdir)

		system('make')
		
	def execute(self, iterations = 1, args = ''):
		for i in range(iterations):
			os.chdir(self.srcdir)
			vars = 'TMPDIR=\"%s\" RESULTDIR=\"%s\"' % (self.tmpdir, self.resultsdir)
			system(vars + ' ./Run ' + args)

		# Do a profiling run if necessary
		profilers = self.job.profilers
		if profilers.present():
			profilers.start(self)
			system(vars + ' ./Run ' + args)
			profilers.stop(self)
			profilers.report(self)
