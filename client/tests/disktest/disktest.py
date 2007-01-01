import test
from autotest_utils import *

class disktest(test.test):
	version = 1

	def setup(self):
		os.mkdir(self.srcdir)
		os.chdir(self.bindir)
		system('cp disktest.c src/')
		os.chdir(self.srcdir)
		system('cc disktest.c -D_FILE_OFFSET_BITS=64 -o disktest')


	def execute(self, iterations = 1):
		system(self.srcdir + '/disktest')
