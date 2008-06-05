from autotest_lib.client.bin import test, autotest_utils, os_dep
from autotest_lib.client.common_lib import utils


class rttester(test.test):
	version = 1

	# http://www.stardust.webpages.pl/files/patches/autotest/rttester.tar.bz2

	def setup(self, tarball = 'rttester.tar.bz2'):
		tarball = autotest_utils.unmap_url(self.bindir, tarball,
		                                   self.tmpdir)
		autotest_utils.extract_tarball_to_dir(tarball, self.srcdir)

	def execute(self):
		os.chdir(self.srcdir)
		utils.system(self.srcdir + '/check-all.sh')
