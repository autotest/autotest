import test
from autotest_utils import *

class stress(test.test):
	version = 1

	# http://weather.ou.edu/~apw/projects/stress/stress-0.18.8.tar.gz
	def setup(self, tarball = 'stress-0.18.8.tar.gz'):
		tarball = unmap_url(self.bindir, tarball, self.tmpdir)
		extract_tarball_to_dir(tarball, self.srcdir)
		os.chdir(self.srcdir)

		system('./configure')
		system('make')
		
	def execute(self, iterations = 1, args_list = '-c 4 -t 50 -v'):
		for i in range(1, iterations+1):
			system(self.srcdir + '/src/stress ' + args)

		# Do a profiling run if necessary
		profilers = self.job.profilers
		if profilers.present():
			profilers.start(self)
			system(self.srcdir + '/src/stress ' + args)
			profilers.stop(self)
			profilers.report(self)
