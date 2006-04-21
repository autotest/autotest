import os, pickle, tempfile
from autotest_utils import *
from error import *

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
		sys.stdout.flush()
		sys.stderr.flush()
		pid = os.fork()
		if pid:			# parent
			(pid, status) = os.waitpid (pid,0)

			ename = self.testdir + "/debug/error-%d" % pid
			if (os.path.exists(ename)):
				fd = file(ename, 'r')
				err = pickle.load(fd)
				fd.close()

				raise err

			if (status != 0):
				raise TestError("test %s failed rc=%d" % (
					testname, status))

		else:			# child
			try:
				os.chdir(self.testdir)
				self.setup()
				self.execute(*parameters)

			except Exception, detail:
				ename = self.testdir + "/debug/error-%d" % (
					os.getpid())
				pickle.dump(detail, open(ename, "w"))
				sys.exit(1)

			sys.exit(0)

	def setup(self):
		pass

