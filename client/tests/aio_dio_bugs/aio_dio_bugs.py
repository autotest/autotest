import os
from autotest_lib.client.bin import test, autotest_utils
from autotest_lib.client.common_lib import utils


# tests is a simple array of "cmd" "arguments"
tests = [["aio-dio-invalidate-failure", "poo"],
	 ["aio-dio-subblock-eof-read", "eoftest"],
	 ["aio-free-ring-with-bogus-nr-pages", ""],
	 ["aio-io-setup-with-nonwritable-context-pointer", ""],
	 ["aio-dio-extend-stat", "file"],
	]
name = 0
arglist = 1

class aio_dio_bugs(test.test):
	version = 5
	preserve_srcdir = True

	def initialize(self):
		self.job.setup_dep(['libaio'])
		ldflags = '-L ' + self.autodir + '/deps/libaio/lib'
		cflags = '-I ' + self.autodir + '/deps/libaio/include'
		self.gcc_flags = ldflags + ' ' + cflags

	def setup(self):
		os.chdir(self.srcdir)
		utils.system('make ' + '"CFLAGS=' + self.gcc_flags + '"')


	def execute(self, args = ''):
		os.chdir(self.tmpdir)
		libs = self.autodir + '/deps/libaio/lib/'
		ld_path = autotest_utils.prepend_path(libs,
                                      autotest_utils.environ('LD_LIBRARY_PATH'))
		var_ld_path = 'LD_LIBRARY_PATH=' + ld_path
		for test in tests:
			cmd = self.srcdir + '/' + test[name] + ' ' \
			      + args + ' ' + test[arglist]
			utils.system(var_ld_path + ' ' + cmd)
