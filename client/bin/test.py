# Copyright Martin J. Bligh, Andy Whitcroft, 2006
#
# Shell class for a test, inherited by all individual tests
#
# Methods:
#	__init__	initialise
#	initialize	run once for each job
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
from parallel import *

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

		self.initialize()
		# compile and install the test, if needed.
		update_version(self.srcdir, self.version, self.setup)


	def initialize(self):
		pass


	def setup(self):
		pass


	def record(self, msg):
		status = self.outputdir + "/status"
		fd = file(status, "w")
		fd.write(msg)
		fd.close()


	def __exec(self, parameters):
		try:
			self.job.stdout.tee_redirect(
				os.path.join(self.debugdir, 'stdout'))
			self.job.stderr.tee_redirect(
				os.path.join(self.debugdir, 'stderr'))

			try:
				os.chdir(self.outputdir)
				self.execute(*parameters)
			finally:
				self.job.stderr.restore()
				self.job.stdout.restore()
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


def testname(url):
	# Extract the testname from the test url.
	match = re.match('[^:]+://(.*)/([^/]*)$', url)
	if not match:
		return ('', url)
	(group, filename) = match.groups()

	# Generate the group prefix.
	gfix = re.compile('\W')
	group = gfix.sub('_', group)
	
	# Drop the extension to get the raw test name.
	tfix = re.compile('\.tgz')
	testname = tfix.sub('', filename)

	return (group, testname)


def __installtest(job, url):
	(group, name) = testname(url)

	##print "group=%s name=%s" % (group, name)

	# Bail if the test is already installed
	group_dir = os.path.join(job.testdir, "download", group)
	if os.path.exists(os.path.join(group_dir, name)):
		return (group, name)

	# If the group directory is missing create it and add
	# an empty  __init__.py so that sub-directories are
	# considered for import.
	if not os.path.exists(group_dir):
		os.mkdir(group_dir)
		f = file(os.path.join(group_dir, '__init__.py'), 'w+')
		f.close()

	print name + ": installing test url=" + url
	system("wget %s -O %s" % (url, os.path.join(group_dir, 'test.tgz')))
	system("cd %s; tar zxf %s" % (group_dir, 'test.tgz'))
	os.unlink(os.path.join(group_dir, 'test.tgz'))

	# For this 'sub-object' to be importable via the name
	# 'group.name' we need to provide an __init__.py,
	# so link the main entry point to this.
	os.symlink(name + '.py', os.path.join(group_dir, name,
				'__init__.py'))

	# The test is now installed.
	return (group, name)


# runtest: main interface for importing and instantiating new tests.
def __runtest(job, tag, url, test_args):
	# If this is not a plain test name then download and install
	# the specified test.
	if is_url(url):
		(group, testname) = __installtest(job, url)
		bindir = os.path.join(job.testdir, "download", group, testname)
	else:
		(group, testname) = ('', url)
		bindir = os.path.join(job.testdir, group, testname)

	outputdir = os.path.join(job.resultdir, testname)

	if (tag):
		outputdir += '.' + tag
	if not os.path.exists(bindir):
		raise TestError(testname + ": test does not exist")
	
	try:
		if group:
			sys.path.insert(0, os.path.join(job.testdir,
								"download"))
			group += '.'
		else:
			sys.path.insert(0, os.path.join(job.testdir, testname))
	
		exec "import %s%s" % (group, testname)
		exec "mytest = %s%s.%s(job, bindir, outputdir)" % \
			(group, testname, testname)
	finally:
		sys.path.pop(0)

	pwd = os.getcwd()
	os.chdir(outputdir)
	mytest.run(testname, test_args)
	os.chdir(pwd)


def runtest(job, tag, url, test_args):
	##__runtest(job, tag, url, test_args)
	pid = fork_start(job.resultdir,
			lambda : __runtest(job, tag, url, test_args))
	fork_waitfor(job.resultdir, pid)
