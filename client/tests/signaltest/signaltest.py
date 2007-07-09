import test
from autotest_utils import *

class signaltest(test.test):
	version = 1
	preserve_srcdir = True

	# git://git.kernel.org/pub/scm/linux/kernel/git/tglx/rt-tests.git

	def setup(self):
		os.chdir(self.srcdir)
		system('make')

	def execute(self, args = '-t 10 -l 100000'):
		system(self.srcdir + '/signaltest ' + args)
