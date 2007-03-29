import test
from autotest_utils import *

# tests is a simple array of "cmd" "arguments"
tests = [["rmaptest", "-h -i100 -n100 -s100 -t100 -V10 -v file1.dat"],
	 ["rmaptest", "-l -i100 -n100 -s100 -t100 -V10 -v file2.dat"],
	 ["rmaptest", "-r -i100 -n100 -s100 -t100 -V10 -v file3.dat"],
	]
name = 0
arglist = 1

class rmaptest(test.test):
	version = 1
	preserve_srcdir = True

	def setup(self):
		os.chdir(self.srcdir)
		system('gcc -Wall -o rmaptest rmap-test.c')


	def execute(self, args = ''):
		os.chdir(self.tmpdir)
		for test in tests:
			cmd = self.srcdir + '/' + test[name] + ' ' \
			      + args + ' ' + test[arglist]
			system(cmd)
