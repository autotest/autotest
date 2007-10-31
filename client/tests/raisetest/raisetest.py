import test
from autotest_utils import *

class raisetest(test.test):
	version = 1

	def execute(self):
		raise 'Arrrrrrrrggggh. You are DOOOMED'
