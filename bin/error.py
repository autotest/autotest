class JobError(Exception):
	pass
class TestError(Exception):
	pass
class CmdError(TestError):
	def __str__(self):
		return "Command <" + self.args[0] + "> failed, rc=%d" % (
			self.args[1])
