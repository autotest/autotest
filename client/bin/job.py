"""The main job wrapper

This is the core infrastructure.
"""

__author__ = """Copyright Andy Whitcroft, Martin J. Bligh 2006"""

# standard stuff
import os, sys, re, pickle, shutil
# autotest stuff
from autotest_utils import *
from parallel import *
import kernel, xen, test, profilers, barrier, filesystem, fd_stack, boottool
import harness, config

class job:
	"""The actual job against which we do everything.

	Properties:
		autodir
			The top level autotest directory (/usr/local/autotest).
			Comes from os.environ['AUTODIR'].
		bindir
			<autodir>/bin/
		testdir
			<autodir>/tests/
		profdir
			<autodir>/profilers/
		tmpdir
			<autodir>/tmp/
		resultdir
			<autodir>/results/<jobtag>
		stdout
			fd_stack object for stdout
		stderr
			fd_stack object for stderr
		profilers
			the profilers object for this job
		harness
			the server harness object for this job
		config
			the job configuration for this job
	"""

	def __init__(self, control, jobtag, cont, harness_type=''):
		"""
			control
				The control file (pathname of)
			jobtag
				The job tag string (eg "default")
			cont
				If this is the continuation of this job
			harness_type
				An alternative server harness
		"""
		self.autodir = os.environ['AUTODIR']
		self.bindir = self.autodir + '/bin'
		self.testdir = self.autodir + '/tests'
		self.profdir = self.autodir + '/profilers'
		self.tmpdir = self.autodir + '/tmp'
		self.resultdir = self.autodir + '/results/' + jobtag

		if not cont:
			if os.path.exists(self.tmpdir):
				system('rm -rf ' + self.tmpdir)
			os.mkdir(self.tmpdir)

			if not os.path.exists(self.autodir + '/results'):
				os.mkdir(self.autodir + '/results')
				
			if os.path.exists(self.resultdir):
				system('rm -rf ' + self.resultdir)
			os.mkdir(self.resultdir)

			os.mkdir(self.resultdir + "/debug")
			os.mkdir(self.resultdir + "/analysis")
			os.mkdir(self.resultdir + "/sysinfo")
			shutil.copyfile(control, self.resultdir + "/control")

		self.control = control
		self.jobtab = jobtag

		self.stdout = fd_stack.fd_stack(1, sys.stdout)
		self.stderr = fd_stack.fd_stack(2, sys.stderr)

		self.config = config.config(self)

		self.harness = harness.select(harness_type, self)

		self.profilers = profilers.profilers(self)

		try:
			tool = self.config_get('boottool.executable')
			self.bootloader = boottool.boottool(tool)
		except:
			pass

		pwd = os.getcwd()
		os.chdir(self.resultdir + "/sysinfo")
		system(self.bindir + '/sysinfo.py')
		os.chdir(pwd)

		self.harness.run_start()


	def harness_select(self, which):
		self.harness = harness.select(which, self)


	def config_set(self, name, value):
		self.config.set(name, value)


	def config_get(self, name):
		return self.config.get(name)

	def setup_dirs(self, results_dir, tmp_dir):
		if not tmp_dir:
			tmp_dir = self.tmpdir + '/build'
		if not os.path.exists(tmp_dir):
			os.mkdir(tmp_dir)
		if not os.path.isdir(tmp_dir):
			raise "Temp dir (%s) is not a dir - args backwards?" \
								% self.tmpdir

		# We label the first build "build" and then subsequent ones 
		# as "build.2", "build.3", etc. Whilst this is a little bit 
		# inconsistent, 99.9% of jobs will only have one build 
		# (that's not done as kernbench, sparse, or buildtest),
		# so it works out much cleaner. One of life's comprimises.
		if not results_dir:
			results_dir = os.path.join(self.resultdir, 'build')
			i = 2
			while os.path.exists(results_dir):
				results_dir = os.path.join(self.resultdir, 'build.%d' % i)
				i += 1
		if not os.path.exists(results_dir):
			os.mkdir(results_dir)

		return (results_dir, tmp_dir)


	def xen(self, base_tree, results_dir = '', tmp_dir = '', leave = False, \
				kjob = None ):
		"""Summon a xen object"""
		(results_dir, tmp_dir) = self.setup_dirs(results_dir, tmp_dir)
		build_dir = 'xen'
		return xen.xen(self, base_tree, results_dir, tmp_dir, build_dir, leave, kjob)


	def kernel(self, base_tree, results_dir = '', tmp_dir = '', leave = False):
		"""Summon a kernel object"""
		(results_dir, tmp_dir) = self.setup_dirs(results_dir, tmp_dir)
		build_dir = 'linux'
		return kernel.kernel(self, base_tree, results_dir, tmp_dir, build_dir, leave)


	def barrier(self, *args):
		"""Create a barrier object"""
		return barrier.barrier(*args)


	def setup_dep(self, deps): 
		"""Set up the dependencies for this test.
		
		deps is a list of libraries required for this test.
		"""
		for dep in deps: 
			try: 
				os.chdir(self.autodir + '/deps/' + dep)
				system('./' + dep + '.py')
			except: 
				error = "setting up dependency " + dep + "\n"
				raise UnhandledError(error)


	def __runtest(self, url, tag, args, dargs):
		try:
			test.runtest(self, url, tag, args, dargs)
		except AutotestError:
			raise
		except:
			raise UnhandledError('running test ' + \
				self.__class__.__name__ + "\n")


	def runtest(self, tag, url, *args):
		raise "Deprecated call to job.runtest. Use run_test instead"


	def run_test(self, url, *args, **dargs):
		"""Summon a test object and run it.
		
		tag
			tag to add to testname
		url
			url of the test to run
		"""

		if not url:
			raise "Test name is invalid. Switched arguments?"
		(group, name) = test.testname(url)
		tag = None
		if dargs.has_key('tag'):
			tag = dargs['tag']
			del dargs['tag']
			if tag:
				name += '.' + tag
		try:
			try:
				self.__runtest(url, tag, args, dargs)
			except Exception, detail:
				self.record("FAIL " + name + " " + \
					detail.__str__() + "\n")

				raise
			else:
				self.record("GOOD " + name + \
					" completed successfully\n")
		except TestError:
			return 0
		except:
			raise
		else:
			return 1


	def filesystem(self, device, mountpoint = None):
		if not mountpoint:
			mountpoint = self.tmpdir
		return filesystem.filesystem(self, device, mountpoint)


	def reboot(self, tag='autotest'):
		self.harness.run_reboot()
		self.bootloader.boot_once(tag)
		system("reboot")
		self.quit()


	def noop(self, text):
		print "job: noop: " + text


	# Job control primatives.

	def __parallel_execute(self, func, *args):
		func(*args)


	def parallel(self, *tasklist):
		"""Run tasks in parallel"""

		pids = []
		for task in tasklist:
			pids.append(fork_start(self.resultdir,
					lambda: self.__parallel_execute(*task)))
		for pid in pids:
			fork_waitfor(self.resultdir, pid)


	def quit(self):
		# XXX: should have a better name.
		self.harness.run_pause()
		raise JobContinue("more to come")


	def complete(self, status):
		"""Clean up and exit"""
		# We are about to exit 'complete' so clean up the control file.
		try:
			os.unlink(self.control + '.state')
		except:
			pass
		self.harness.run_complete()
		sys.exit(status)


	steps = []
	def next_step(self, step):
		"""Define the next step"""
		step[0] = step[0].__name__
		self.steps.append(step)
		pickle.dump(self.steps, open(self.control + '.state', 'w'))


	def step_engine(self):
		"""the stepping engine -- if the control file defines
		step_init we will be using this engine to drive multiple runs.
		"""
		"""Do the next step"""
		lcl = dict({'job': self})

		str = """
from error import *
from autotest_utils import *
"""
		exec(str, lcl, lcl)
		execfile(self.control, lcl, lcl)

		state = self.control + '.state'
		# If there is a mid-job state file load that in and continue
		# where it indicates.  Otherwise start stepping at the passed
		# entry.
		try:
			self.steps = pickle.load(open(state, 'r'))
		except:
			if lcl.has_key('step_init'):
				self.next_step([lcl['step_init']])

		# Run the step list.
		while len(self.steps) > 0:
			step = self.steps.pop(0)
			pickle.dump(self.steps, open(state, 'w'))

			cmd = step.pop(0)
			cmd = lcl[cmd]
			lcl['__cmd'] = cmd
			lcl['__args'] = step
			exec("__cmd(*__args)", lcl, lcl)


	def record(self, msg):
		"""Record job-level status"""

		msg = msg.rstrip()
		# Ensure any continuation lines are marked so we can
		# detect them in the status file to ensure it is parsable.
		msg = re.sub(r"\n", "\n  ", msg)

		self.harness.test_status(msg)
		print msg
		status = self.resultdir + "/status"
		file(status, "a").write(msg + "\n")


def runjob(control, cont = False, tag = "default", harness_type = ''):
	"""The main interface to this module

	control
		The control file to use for this job.
	cont
		Whether this is the continuation of a previously started job
	"""
	state = control + '.state'

	# instantiate the job object ready for the control file.
	myjob = None
	try:
		# Check that the control file is valid
		if not os.path.exists(control):
			raise JobError(control + ": control file not found")

		# When continuing, the job is complete when there is no
		# state file, ensure we don't try and continue.
		if cont and not os.path.exists(state):
			sys.exit(1)
		if cont == False and os.path.exists(state):
			os.unlink(state)

		myjob = job(control, tag, cont, harness_type)

		# Load in the users control file, may do any one of:
		#  1) execute in toto
		#  2) define steps, and select the first via next_step()
		myjob.step_engine()

	except JobContinue:
		sys.exit(5)

	except JobError, instance:
		print "JOB ERROR: " + instance.args[0]
		if myjob != None:
			myjob.record("ABORT " + instance.args[0] + "\n")
			myjob.complete(1)

	except:
		if myjob:
			myjob.harness.run_abort()
		# Ensure we cannot continue this job, it is in rictus.
		if os.path.exists(state):
			os.unlink(state)
		raise

	# If we get here, then we assume the job is complete and good.
	myjob.complete(0)

