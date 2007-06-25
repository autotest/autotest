import test
from autotest_utils import *

class fsfuzzer(test.test):
	version = 1

	# http://people.redhat.com/sgrubb/files/fsfuzzer-0.6.tar.gz
	def setup(self, tarball = 'fsfuzzer-0.6.tar.gz'):
		tarball = unmap_url(self.bindir, tarball, self.tmpdir)
		extract_tarball_to_dir(tarball, self.srcdir)
		os.chdir(self.srcdir)

		system('make')
		
	def execute(self, iterations = 1, fstype = 'iso9660'):
		profilers = self.job.profilers
		args = fstype + ' 1'
		if not profilers.only():
			for i in range(iterations):
				system(self.srcdir + '/run_test ' + args)

		# Do a profiling run if necessary
		if profilers.present():
			profilers.start(self)
			system(self.srcdir + '/run_test ' + args)
			profilers.stop(self)
			profilers.report(self)
