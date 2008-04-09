# POSIX test suite wrapper class. More information about the suite can be found
# at http://posixtest.sourceforge.net/
import test, os
from autotest_utils import *

__author__ = '''mohd.omar@in.ibm.com (Mohammed Omar)'''

class posixtest(test.test):
	version = 1
	# http://ufpr.dl.sourceforge.net/sourceforge/posixtest/posixtestsuite-1.5.2.tar.gz
	def setup(self, tarball = 'posixtestsuite-1.5.2.tar.gz'):
		self.posix_tarball = unmap_url(self.bindir, tarball, self.tmpdir)
		extract_tarball_to_dir(self.posix_tarball, self.srcdir)
		os.chdir(self.srcdir)
		# Applying a small patch that introduces some linux specific
		# linking options
		system('patch -p1 < ../posix-linux.patch')
		system('make')


	def execute(self):
		os.chdir(self.srcdir)
		system('./run_tests THR')

