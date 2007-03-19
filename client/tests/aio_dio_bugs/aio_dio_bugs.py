import test
from autotest_utils import *

# tests is a simple array of "cmd" "arguments"
tests = [["aio-dio-invalidate-failure", "poo"],]
name = 0
arglist = 1

class aio_dio_bugs(test.test):
	version = 1

	def initialize(self):
		self.job.setup_dep(['libaio'])
		ldflags = '-L ' + self.autodir + '/deps/libaio/lib'
		cflags = '-I ' + self.autodir + '/deps/libaio/include'
		self.gcc_flags = ldflags + ' ' + cflags

	def setup(self):
		os.mkdir(self.srcdir)
		os.chdir(self.bindir)
		system('cp Makefile *.c src/')
		os.chdir(self.srcdir)
		system('make')


	def execute(self, args = ''):
		os.chdir(self.tmpdir)
		libs = self.autodir+'/deps/libaio/lib/'
		ld_path = prepend_path(libs, environ('LD_LIBRARY_PATH'))
		var_ld_path = 'LD_LIBRARY_PATH=' + ld_path
		for test in tests:
			cmd = self.srcdir + '/' + test[name] + ' ' \
			      + args + ' ' + test[arglist]
			system(var_ld_path + ' ' + cmd)
