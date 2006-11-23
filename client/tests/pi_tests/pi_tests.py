import test
from autotest_utils import *

class pi_tests(test.test):
	version = 1

	# http://www.stardust.webpages.pl/files/patches/autotest/pi_tests.tar.bz2

	def setup(self, tarball = 'pi_tests.tar.bz2'):
		check_glibc_ver('2.5')
		tarball = unmap_url(self.bindir, tarball, self.tmpdir)
		extract_tarball_to_dir(tarball, self.srcdir)
		os.chdir(self.srcdir)

		system('make')

	def execute(self, args = '1 300'):
		os.chdir(self.srcdir)
		system('./start.sh ' + args)
