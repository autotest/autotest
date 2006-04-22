import test
from autotest_utils import *

class bonnie(test.test):
	def setup(self)

	def execute(self, iterations = 1, extra_args = None, user = 'root');

		args = ['-d ' + self.tmp_dir]
		args.append('-u ' + user)
		args.append(extra_args)
		os.system('./bonnie++ -d ' + ' '.join(args))

		for i in range(1, iterations+1):
			
			kernel.build_timed(threads, '../log/time.%d' % i)
