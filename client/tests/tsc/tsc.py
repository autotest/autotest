import test
from autotest_utils import *

class tsc(test.test):
	version = 1

	def setup(self, tarball = 'checktsc.tar'):
		tarball = unmap_url(self.bindir, tarball, self.tmpdir)
		extract_tarball_to_dir(tarball, self.srcdir)
		os.chdir(self.srcdir)
		system('make')

	
	def execute(self, iterations = 1, args = '--silent'):
		for i in range(iterations):
			system(self.srcdir + '/checktsc ' + args)
