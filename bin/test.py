import os, pickle, tempfile
from autotest_utils import *
from error import *

class test:
	def __init__(self, job, testdir):
		self.job = job
		self.tests = job.autodir + '/tests'
		self.testdir = job.resultdir + '/' + testdir
		os.mkdir(self.testdir)
		self.resultsdir = self.testdir + "/results"
		os.mkdir(self.resultsdir)
		self.profdir = self.testdir + "/profiling"
		os.mkdir(self.profdir)
		self.debugdir = self.testdir + "/debug"
		os.mkdir(self.debugdir)
		self.tmpdir = self.testdir + "/tmp"
		os.mkdir(self.tmpdir)

	def __exec(self, parameters):
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
					self.__class__.__name__, status))

		else:			# child
			try:
				try:
					os.chdir(self.testdir)
					self.execute(*parameters)

				except AutotestError:
					raise

				except:
					raise UnhandledError('running test ' + \
						self.__class__.__name__ + "\n")

			except Exception, detail:
				ename = self.testdir + "/debug/error-%d" % (
					os.getpid())
				pickle.dump(detail, open(ename, "w"))
				sys.exit(1)

			sys.exit(0)

##	def __exec(self, parameters):
##		try:
##			os.chdir(self.testdir)
##			self.setup()
##			self.execute(*parameters)
##		except AutotestError:
##			raise
##		except:
##			raise UnhandledError('running test ' + \
##				self.__class__.__name__ + "\n")

	def setup(self):
		pass

	def run(self, testname, parameters):
		status = self.testdir + "/status"
		try:
			self.__exec(parameters)
		except Exception, detail:
			fd = file(status, "w")
			fd.write("FAIL " + detail.__str__() + "\n")
			fd.close()

			raise
		else:
			fd = file(status, "w")
			fd.write("GOOD Completed Successfully\n")
			fd.close()


# runtest: main interface for importing and instantiating new tests.
def runtest(self, tag, testname, test_args):
	testd = self.testdir + '/'+ testname
	if not os.path.exists(testd):
		raise TestError(testname + ": test does not exist")
	
	try:
		sys.path.insert(0, testd)

		exec "import %s" % testname
		exec "mytest = %s.%s(self, testname + '.' + tag)" % \
			(testname, testname)

		mytest.bindir = self.testdir + '/' + testname
		mytest.srcdir = mytest.bindir + '/src'
		mytest.tmpdir = self.tmpdir + '/' + testname
		if os.path.exists(mytest.tmpdir):
			system('rm -rf ' + mytest.tmpdir)
		os.mkdir(mytest.tmpdir)

		versionfile = mytest.srcdir + '/.version'
		newversion = mytest.version
		if os.path.exists(versionfile):
			existing_version = pickle.load(open(versionfile, 'r'))
			if (existing_version != newversion):
				system('rm -rf ' + mytest.srcdir)
		if not os.path.exists(mytest.srcdir):
			# DANGER, will robinson. Error catching here ????
			mytest.setup()
			if os.path.exists(mytest.srcdir):
				pickle.dump(newversion, open(versionfile, 'w'))
		mytest.run(testname, test_args)

	finally:
		sys.path.pop(0)
