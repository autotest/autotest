# Copyright Martin J. Bligh, Andy Whitcroft, 2006
#
# Shell class for a test, inherited by all individual tests
#
# Methods:
#	__init__	initialise
#	initialize	run once for each job
#	setup		run once for each new version of the test installed
#	run		run the test (wrapped by job.run_test())
#
# Data:
#	job		backreference to the job this test instance is part of
#	outputdir	eg. results/<job>/<testname.tag>
#	resultsdir	eg. results/<job>/<testname.tag>/results
#	profdir		eg. results/<job>/<testname.tag>/profiling
#	debugdir	eg. results/<job>/<testname.tag>/debug
#	bindir		eg. tests/<test>
#	src		eg. tests/<test>/src
#	tmpdir		eg. tmp/<testname.tag>

import os, pickle, tempfile, fcntl, traceback
from autotest_utils import *
from common.error import *
import sysinfo

class test:
	preserve_srcdir = False

	def __init__(self, job, bindir, outputdir):
		self.job = job
		self.autodir = job.autodir

		self.outputdir = outputdir
		tagged_testname = os.path.basename(self.outputdir)
		# check if the outputdir already exists, because if it does
		# then this test has already been run with the same tag earlier
		# in this job
		if os.path.exists(self.outputdir):
			testname, tag = (tagged_testname + '.').split('.', 1)
			msg = ("%s already exists, test <%s> may have already "
			       + "run with tag <%s>") % (tagged_testname,
							 testname, tag)
			raise TestError(msg)
		else:
			os.mkdir(self.outputdir)

		self.resultsdir = os.path.join(self.outputdir, 'results')
		os.mkdir(self.resultsdir)
		self.profdir = os.path.join(self.outputdir, 'profiling')
		os.mkdir(self.profdir)
		self.debugdir = os.path.join(self.outputdir, 'debug')
		os.mkdir(self.debugdir)
		self.bindir = bindir
		self.libdir = job.libdir
		self.srcdir = os.path.join(self.bindir, 'src')

		self.tmpdir = os.path.join(job.tmpdir, tagged_testname)

		if os.path.exists(self.tmpdir):
			system('rm -rf ' + self.tmpdir)
		os.mkdir(self.tmpdir)

		self.job.stdout.tee_redirect(
			os.path.join(self.debugdir, 'stdout'))
		self.job.stderr.tee_redirect(
			os.path.join(self.debugdir, 'stderr'))
		try:
			self.initialize()
			# compile and install the test, if needed.
			update_version(self.srcdir, self.preserve_srcdir,
						self.version, self.setup)
		finally:
			self.job.stderr.restore()
			self.job.stdout.restore()


	def assert_(self, expr, msg='Assertion failed.'):
		if not expr:
			raise TestError(msg)


	def write_keyval(self, dictionary):
		write_keyval(self.resultsdir, dictionary)


	def initialize(self):
		pass


	def setup(self):
		pass


	def cleanup(self):
		pass


	def _exec(self, args, dargs):
		try:
			self.job.stdout.tee_redirect(
				os.path.join(self.debugdir, 'stdout'))
			self.job.stderr.tee_redirect(
				os.path.join(self.debugdir, 'stderr'))

			try:
				os.chdir(self.outputdir)
				write_keyval(self.outputdir,
						{ 'version' : self.version })
				self.execute(*args, **dargs)
			finally:
				self.cleanup()
				self.job.stderr.restore()
				self.job.stdout.restore()
		except AutotestError:
			raise
		except:
			raise UnhandledError('running test ' + \
				self.__class__.__name__ + "\n")


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
def runtest(job, url, tag, args, dargs):
	# If this is not a plain test name then download and install
	# the specified test.
	if is_url(url):
		(group, testname) = __installtest(job, url)
		bindir = os.path.join(job.testdir, "download", group, testname)
	else:
		# If the test is local, it can be located on the tests dir or the 
		# site_tests dir. Tests on site_tests override what's defined on tests.
		(group, testname) = ('', url)
		bindir = os.path.join(job.testdir, group, testname)
		site_bindir = os.path.join(job.site_testdir, group, testname)

	outputdir = os.path.join(job.resultdir, testname)

	if (tag):
		outputdir += '.' + tag

	# If we can find the test on site_tests, we prefer this version over the
	# others. If test is in none of these directories, then throw an exception.
	if os.path.exists(site_bindir):
		bindir = site_bindir
		job.testdir = job.site_testdir
	elif not os.path.exists(bindir):
		raise TestError(testname + ": test does not exist")

	if group:
		sys.path.insert(0, os.path.join(job.testdir, "download"))
		group += '.'
	else:
		sys.path.insert(0, os.path.join(job.testdir, testname))
	
	try:
		lockfile = open(os.path.join(job.tmpdir, ".testlock"), "w")
		fcntl.flock(lockfile, fcntl.LOCK_EX)
		exec "import %s%s" % (group, testname)
		exec "mytest = %s%s.%s(job, bindir, outputdir)" % \
			(group, testname, testname)
	finally:
		fcntl.flock(lockfile, fcntl.LOCK_UN)
		lockfile.close()
		sys.path.pop(0)

	pwd = os.getcwd()
	os.chdir(outputdir)
	dmesg = os.path.join(mytest.debugdir, 'dmesg')
	try:
		mytest._exec(args, dargs)
	finally:
		try:
			sysinfo_dir = os.path.join(mytest.outputdir, 'sysinfo')
			sysinfo.log_after_each_test(sysinfo_dir,
							mytest.job.sysinfodir)

			if os.path.exists(mytest.tmpdir):
				system('rm -rf ' + mytest.tmpdir)
		except:
			print 'post-test error:'
			traceback.print_exc(file=sys.stdout)
