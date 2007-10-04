import test
import os
from autotest_utils import *

class ltp(test.test):
	version = 3

	# http://prdownloads.sourceforge.net/ltp/ltp-full-20070731.tgz
	def setup(self, tarball = 'ltp-full-20070731.tar.bz2'):
		tarball = unmap_url(self.bindir, tarball, self.tmpdir)
		extract_tarball_to_dir(tarball, self.srcdir)
		os.chdir(self.srcdir)

		system('patch -p1 < ../ltp.patch')
		system('cp ../scan.c pan/')   # saves having lex installed
		system('make -j %d' % count_cpus())
		system('yes n | make install')


	# Note: to run a specific test, try '-f cmdfile -s test' in the
	# in the args (-f for test file and -s for the test case)
	# eg, job.run_test('ltp', '-f math -s float_bessel')
	def execute(self, args = ''):
		logfile = os.path.join(self.resultsdir, 'ltp.log')
		failcmdfile = os.path.join(self.debugdir, 'failcmdfile')

		args = '-q -l ' + logfile + ' -C ' + failcmdfile + ' ' + args
		cmd = os.path.join(self.srcdir, 'runltp') + ' ' + args

		profilers = self.job.profilers
		if profilers.present():
			profilers.start(self)
		system(cmd)
		if profilers.present():
			profilers.stop(self)
			profilers.report(self)
