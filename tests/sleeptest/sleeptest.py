import test, time
from autotest_utils import *

class sleeptest(test.test):
	version = 1

	def execute(self, seconds = 1):
		profilers = self.job.profilers
		profilers.start(self)
		time.sleep(seconds)
		profilers.stop(self)
		profilers.report(self)
