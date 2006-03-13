import os
from autotest_utils import *

class test:
	def __init__(self, job, testdir):
		self.job = job
		self.testdir = job.resultdir + '/' + testdir
		os.mkdir(self.testdir)
		os.mkdir(self.testdir + "/results")
		os.mkdir(self.testdir + "/profiling")
		os.mkdir(self.testdir + "/debug")
		os.mkdir(self.testdir + "/analysis")


	def run(self, testname, parameters):
		os.chdir(self.testdir)
		pid = os.fork()
		if pid:			# parent
			os.waitpid (pid,0)
		else:			# child
			self.setup()
			self.execute()
