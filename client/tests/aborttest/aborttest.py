import test
from autotest_utils import *

class aborttest(test.test):
	version = 1

	def execute(self):
		raise JobError('Arrrrrrrrggggh. You are DOOOMED')
