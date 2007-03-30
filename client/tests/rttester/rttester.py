import test, os_dep
from autotest_utils import *

class rttester(test.test):
	version = 1

	# http://www.stardust.webpages.pl/files/patches/autotest/rttester.tar.bz2

	def setup(self, tarball = 'rttester.tar.bz2'):
		tarball = unmap_url(self.bindir, tarball, self.tmpdir)
		extract_tarball_to_dir(tarball, self.srcdir)

	def execute(self):
		os.chdir(self.srcdir)
		system(self.srcdir + '/check-all.sh')
