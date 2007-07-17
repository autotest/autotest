import test
from autotest_utils import *

class fsstress(test.test):
	version = 1

	# http://www.zip.com.au/~akpm/linux/patches/stuff/ext3-tools.tar.gz
	def setup(self, tarball = 'ext3-tools.tar.gz'):
		self.tarball = unmap_url(self.bindir, tarball, self.tmpdir)
		extract_tarball_to_dir(self.tarball, self.srcdir)

		os.chdir(self.srcdir)
		system('patch -p1 < ../fsstress-ltp.patch')
		system('make fsstress')


	def execute(self, testdir = None, extra_args = '', nproc = '1000', nops = '1000'):
		if not testdir:
			testdir = self.tmpdir

		args = '-d ' + testdir + ' -p ' + nproc + ' -n ' + nops + ' ' + extra_args

		cmd = self.srcdir + '/fsstress ' + args
		profilers = self.job.profilers
		if not profilers.only():
			system(cmd)

		# Do a profiling run if necessary
		if profilers.present():
			profilers.start(self)
			system(cmd)
			profilers.stop(self)
			profilers.report(self)
