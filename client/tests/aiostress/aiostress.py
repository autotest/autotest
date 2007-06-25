# This requires aio headers to build.
# Should work automagically out of deps now.

# NOTE - this should also have the ability to mount a filesystem, 
# run the tests, unmount it, then fsck the filesystem

import test
from autotest_utils import *

class aiostress(test.test):
	version = 2

	def initialize(self):
		self.job.setup_dep(['libaio'])
		ldflags = '-L ' + self.autodir + '/deps/libaio/lib'
		cflags = '-I ' + self.autodir + '/deps/libaio/include'
		self.gcc_flags = ldflags + ' ' + cflags


	# ftp://ftp.suse.com/pub/people/mason/utils/aio-stress.c
	def setup(self, tarball = None):
		print self.srcdir, self.bindir, self.tmpdir
		os.mkdir(self.srcdir)
		os.chdir(self.srcdir)
		system('cp ' + self.bindir+'/aio-stress.c .')
		os.chdir(self.srcdir)
		self.gcc_flags += ' -Wall -lpthread -laio'
		system('gcc ' + self.gcc_flags + ' aio-stress.c -o aio-stress')


	def execute(self, args = ''):
		os.chdir(self.tmpdir)
		libs = self.autodir+'/deps/libaio/lib/'
		ld_path = prepend_path(libs, environ('LD_LIBRARY_PATH'))
		var_ld_path = 'LD_LIBRARY_PATH=' + ld_path
		cmd = self.srcdir + '/aio-stress ' + args + ' poo'
		profilers = self.job.profilers
		if not profilers.only():
			system(var_ld_path + ' ' + cmd)

		# Do a profiling run if necessary
		if profilers.present():
			profilers.start(self)
			system(var_ld_path + ' ' + cmd)
			profilers.stop(self)
			profilers.report(self)
