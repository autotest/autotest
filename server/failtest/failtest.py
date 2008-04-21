import test

class failtest(test.test):
	version = 1

	def execute(self):
		raise "I failed! I failed!"
