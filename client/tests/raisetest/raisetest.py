from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import error


class raisetest(test.test):
	version = 1

	def execute(self):
		raise error.TestError('Arrrrrrrrggggh. You are DOOOMED')
