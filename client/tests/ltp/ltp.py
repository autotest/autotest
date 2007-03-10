# needs lex installed to compile ltp
import test
from autotest_utils import *

class ltp(test.test):
	version = 2

	# http://prdownloads.sourceforge.net/ltp/ltp-full-20060918.tgz
	def setup(self, tarball = 'ltp-full-20060918.tar.bz2'):
		tarball = unmap_url(self.bindir, tarball, self.tmpdir)
		extract_tarball_to_dir(tarball, self.srcdir)
		os.chdir(self.srcdir)

		system('patch -p1 < ../ltp.patch')
		system('cp ../scan.c pan/')
		system('make -j %d' % count_cpus())
		system('yes n | make install')

	# Note: to run a specific test, try '-f test' in the args
	# eg, job.run_test('ltp', '-f ballista')
	def execute(self, args = ''):
		logfile = self.resultsdir + '/ltp.log'
		args = '-q -l ' + logfile + ' ' + args
		system("yes '' | " + self.srcdir + '/runltp ' + args)
