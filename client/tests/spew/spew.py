import os
from autotest_lib.client.bin import test, autotest_utils
from autotest_lib.client.common_lib import utils


class spew(test.test):
	version = 1

	# ftp://ftp.berlios.de/pub/spew/1.0.5/spew-1.0.5.tgz
	def setup(self, tarball = 'spew-1.0.5.tgz'):
		self.tarball = autotest_utils.unmap_url(self.bindir, tarball,
		                                        self.tmpdir)
		autotest_utils.extract_tarball_to_dir(self.tarball, self.srcdir)

		os.chdir(self.srcdir)
		utils.system('./configure')
		utils.system('make')


	def execute(self, testdir = None, iterations = 1, filesize='100M', type='write', pattern='random'):
		cmd = os.path.join(self.srcdir, 'src/spew')
		if not testdir:
			testdir = self.tmpdir
		tmpfile = os.path.join(testdir, 'spew-test.%d' % os.getpid())
		results = os.path.join(self.resultsdir, 'stdout')
		args = '--%s -i %d -p %s -b 2k -B 2M %s %s' % \
				(type, iterations, pattern, filesize, tmpfile)
		cmd += ' ' + args

		# Do a profiling run if necessary
		profilers = self.job.profilers
		if profilers.present():
			profilers.start(self)

		open(self.resultsdir + '/command', 'w').write(cmd + '\n')
		self.job.stdout.redirect(results)
		try:
			utils.system(cmd)
		finally:
			self.job.stdout.restore()

		if profilers.present():
			profilers.stop(self)
			profilers.report(self)
