import test
from autotest_utils import *

class cyclictest(test.test):
	version = 1

	# http://tglx.de/projects/misc/cyclictest/cyclictest-v0.11.tar.bz2

	def setup(self, tarball = 'cyclictest-v0.11.tar.bz2'):
		tarball = unmap_url(self.bindir, tarball, self.tmpdir)
		extract_tarball_to_dir(tarball, self.srcdir)
		os.chdir(self.srcdir)

		system('make')

	def execute(self, args = '-t 10 -l 100000'):
		system(self.srcdir + '/cyclictest ' + args)
