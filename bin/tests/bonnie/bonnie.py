import test
from autotest_utils import *

class bonnie(test.test):
	def setup(self)
		self.tarball = self.bindir + 'bonnie++-1.03a.tgz'
		# http://www.coker.com.au/bonnie++/bonnie++-1.03a.tgz
		os.chdir(self.srcdir . '/..')
		system_raise('tar ztf ' + self.tarball)
		os.rename('bonnie++-1.03a/', self.srcdir)
		os.chdir(self.srcdir)

		system_raise('./configure')
		system_raise('make')
		
	def execute(self, iterations = 1, extra_args = None, user = 'root');
		args = ['-d ' + self.tmp_dir]
		args.append('-u ' + user)
		args.append(extra_args)
		system_raise(self.srcdir + '/bonnie++ ' + ' '.join(args))

		for i in range(1, iterations+1):
			kernel.build_timed(threads, '../log/time.%d' % i)
