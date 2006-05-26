import os, pickle, tempfile
from autotest_utils import *
from error import *

class test:
	def __init__(self, job, outputdir):
		testname = self.__class__.__name__

		self.job = job
		self.tests = job.autodir + '/tests'
		self.outputdir = outputdir
		os.mkdir(self.outputdir)
		self.resultsdir = self.outputdir + "/results"
		os.mkdir(self.resultsdir)
		self.profdir = self.outputdir + "/profiling"
		os.mkdir(self.profdir)
		self.debugdir = self.outputdir + "/debug"
		os.mkdir(self.debugdir)

		self.bindir = job.resultdir + '/' + testname
		self.srcdir = self.bindir + '/src'

		self.tmpdir = job.tmpdir + '/' + testname
		if os.path.exists(self.tmpdir):
			system('rm -rf ' + self.tmpdir)
		os.mkdir(self.tmpdir)

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
		exec "mytest = %s.%s(job, outputdir)" % \
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
