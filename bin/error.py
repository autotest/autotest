# AutotestError: the parent of all errors deliberatly thrown
# within the client code.
class AutotestError(Exception):
	pass

# JobError: indicates an error which terminates and fails the whole job.
class JobError(AutotestError):
	pass

# TestError: indicates an error which terminates and fails the test.
class TestError(AutotestError):
	pass

# CmdError: indicates that a command failed, is fatal to the test
# unless caught.
class CmdError(TestError):
	def __str__(self):
		return "Command <" + self.args[0] + "> failed, rc=%d" % (
			self.args[1])
