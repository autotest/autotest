import sys
from traceback import format_exception

# Allow us to bail out requesting continuance.
class JobContinue(SystemExit):
	pass

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
		return "Command <" + self.args[0] + "> failed, rc=%d" % (self.args[1])

# UnhandledError: indicates an unhandled exception in a test.
class UnhandledError(TestError):
	def __init__(self, prefix):
		t, o, tb = sys.exc_info()
		trace = format_exception(t, o, tb)
		# Clear the backtrace to prevent a circular reference
		# in the heap -- as per tutorial
		tb = ''

		msg = prefix
		for line in trace:
			msg = msg + line

		self.args = msg
