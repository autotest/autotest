# Copyright Martin J. Bligh, Andy Whitcroft, 2006
#
# Shell class for a test, inherited by all individual tests
#
# Methods:
#	__init__	initialise
#	setup		run once for each new version of the test installed
#	record		record an entry in the status file
#	run		run the test (wrapped by job.runtest())
#
# Data:
#	job		backreference to the job this test instance is part of
#	outputdir	eg. results/<job>/<testname.tag>
#	resultsdir	eg. results/<job>/<testname.tag>/results
#	profdir		eg. results/<job>/<testname.tag>/profiling
#	debugdir	eg. results/<job>/<testname.tag>/debug
#	bindir		eg. tests/<test>
#	src		eg. tests/<test>/src
#	tmpdir		eg. tmp/<test>

import os, pickle, tempfile
from autotest_utils import *
from error import *

class test:
	def __init__(self, job, bindir, outputdir):
		testname = self.__class__.__name__

		self.job = job
		self.autodir = job.autodir
		self.outputdir = outputdir
		os.mkdir(self.outputdir)
		self.resultsdir = self.outputdir + "/results"
		os.mkdir(self.resultsdir)
		self.profdir = self.outputdir + "/profiling"
		os.mkdir(self.profdir)
		self.debugdir = self.outputdir + "/debug"
		os.mkdir(self.debugdir)

		self.bindir = bindir
		self.srcdir = bindir + '/src'

		self.tmpdir = job.tmpdir + '/' + testname
		if os.path.exists(self.tmpdir):
			system('rm -rf ' + self.tmpdir)
		os.mkdir(self.tmpdir)

		# compile and install the test, if needed.
		update_version(self.srcdir, self.version, self.setup)


	def setup(self):
		pass


	def record(self, msg):
		status = self.outputdir + "/status"
		fd = file(status, "w")
		fd.write(msg)
		fd.close()

	def __exec(self, parameters):
		try:
			os.chdir(self.outputdir)
			self.execute(*parameters)
		except AutotestError:
			raise
		except:
			raise UnhandledError('running test ' + \
				self.__class__.__name__ + "\n")

	def run(self, testname, parameters):
		try:
			self.__exec(parameters)
		except Exception, detail:
			self.record("FAIL " + detail.__str__() + "\n")

			raise
		else:
			self.record("GOOD Completed Successfully\n")


def fork_lambda(tmp, l):
	sys.stdout.flush()
	sys.stderr.flush()
	pid = os.fork()
	if pid:			# parent
		(pid, status) = os.waitpid (pid,0)

		ename = tmp + "/debug/error-%d" % pid
		if (os.path.exists(ename)):
			fd = file(ename, 'r')
			err = pickle.load(fd)
			fd.close()

			raise err

		if (status != 0):
			raise TestError("test failed rc=%d" % (status))

	else:			# child
		try:
			try:
				l()

			except AutotestError:
				raise

			except:
				raise UnhandledError("test failed and threw:\n")

		except Exception, detail:
			ename = tmp + "/debug/error-%d" % (
				os.getpid())
			pickle.dump(detail, open(ename, "w"))

			sys.stdout.flush()
			sys.stderr.flush()
			os._exit(1)

		sys.stdout.flush()
		sys.stderr.flush()
		os._exit(0)

# runtest: main interface for importing and instantiating new tests.
def __runtest(job, tag, testname, test_args):
	bindir = job.testdir + '/' + testname
	outputdir = job.resultdir + '/' + testname
	if (tag):
		outputdir += '.' + tag
	if not os.path.exists(bindir):
		raise TestError(testname + ": test does not exist")
	
	try:
		sys.path.insert(0, bindir)
	
		exec "import %s" % (testname)
		exec "mytest = %s.%s(job, bindir, outputdir)" % \
			(testname, testname)
	finally:
		sys.path.pop(0)

	pwd = os.getcwd()
	os.chdir(outputdir)
	mytest.run(testname, test_args)
	os.chdir(pwd)


def runtest(job, tag, testname, test_args):
	##__runtest(job, tag, testname, test_args)
	fork_lambda(job.resultdir,
		lambda : __runtest(job, tag, testname, test_args))
