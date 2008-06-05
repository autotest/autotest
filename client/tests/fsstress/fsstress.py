from autotest_lib.client.bin import test, autotest_utils
from autotest_lib.client.common_lib import utils



class fsstress(test.test):
	version = 1

	# http://www.zip.com.au/~akpm/linux/patches/stuff/ext3-tools.tar.gz
	def setup(self, tarball = 'ext3-tools.tar.gz'):
		self.tarball = autotest_utils.unmap_url(self.bindir, tarball,
		                                        self.tmpdir)
		autotest_utils.extract_tarball_to_dir(self.tarball, self.srcdir)

		os.chdir(self.srcdir)
		utils.system('patch -p1 < ../fsstress-ltp.patch')
		utils.system('make fsstress')


	def execute(self, testdir = None, extra_args = '', nproc = '1000', nops = '1000'):
		if not testdir:
			testdir = self.tmpdir

		args = '-d ' + testdir + ' -p ' + nproc + ' -n ' + nops + ' ' + extra_args

		cmd = self.srcdir + '/fsstress ' + args
		profilers = self.job.profilers
		if not profilers.only():
			utils.system(cmd)

		# Do a profiling run if necessary
		if profilers.present():
			profilers.start(self)
			utils.system(cmd)
			profilers.stop(self)
			profilers.report(self)
