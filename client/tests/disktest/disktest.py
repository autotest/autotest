import test
from autotest_utils import *

class disktest(test.test):
	version = 1

	def setup(self):
		os.mkdir(self.srcdir)
		os.chdir(self.bindir)
		system('cp disktest.c src/')
		os.chdir(self.srcdir)
		cflags = '-D_FILE_OFFSET_BITS=64 -D _GNU_SOURCE'
		system('cc disktest.c ' + cflags + ' -o disktest')


	def execute(self, iterations = 1):
		system(self.srcdir + '/disktest')
