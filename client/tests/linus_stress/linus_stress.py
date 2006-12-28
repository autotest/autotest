import test
from autotest_utils import *

class linus_stress(test.test):
	version = 1

	def setup(self):
		os.mkdir(self.srcdir)
		os.chdir(self.bindir)
		system('cp linus_stress.c src/')
		os.chdir(self.srcdir)
		system('cc linus_stress.c -D_POSIX_C_SOURCE=200112 -o linus_stress')


	def execute(self, iterations = 1):
		profilers = self.job.profilers
		if profilers.present():
			profilers.start(self)
		for i in range(iterations):
			system(os.path.join(self.srcdir, 'linus_stress'))
		if profilers.present():
			profilers.stop(self)
			profilers.report(self)
