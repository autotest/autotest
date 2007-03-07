import test
from autotest_utils import *

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
		system('cp aio-dio-invalidate-failure.c src/')
		os.chdir(self.srcdir)
		self.gcc_flags += ' -Wall -lpthread -laio'
		system('gcc ' + self.gcc_flags + ' aio-dio-invalidate-failure.c -o aio-dio-invalidate-failure')


	def execute(self, args = ''):
		os.chdir(self.tmpdir)
		libs = self.autodir+'/deps/libaio/lib/'
		ld_path = prepend_path(libs, environ('LD_LIBRARY_PATH'))
		var_ld_path = 'LD_LIBRARY_PATH=' + ld_path
		cmd = self.srcdir + '/aio-dio-invalidate-failure ' + args + ' poo'
		system(var_ld_path + ' ' + cmd)
