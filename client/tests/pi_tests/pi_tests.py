from autotest_lib.client.bin import test, autotest_utils
from autotest_lib.client.common_lib import utils


class pi_tests(test.test):
	version = 1

	# http://www.stardust.webpages.pl/files/patches/autotest/pi_tests.tar.bz2

	def setup(self, tarball = 'pi_tests.tar.bz2'):
		check_glibc_ver('2.5')
		tarball = autotest_utils.unmap_url(self.bindir, tarball,
		                                   self.tmpdir)
		autotest_utils.extract_tarball_to_dir(tarball, self.srcdir)
		os.chdir(self.srcdir)

		utils.system('make')

	def execute(self, args = '1 300'):
		os.chdir(self.srcdir)
		utils.system('./start.sh ' + args)
