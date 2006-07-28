"""The main job wrapper

This is the core infrastructure.
"""

__author__ = """Copyright Andy Whitcroft, Martin J. Bligh 2006"""

from autotest_utils import *
import os, sys, kernel, test, pickle, threading, profilers

class AsyncRun(threading.Thread):
    """Parallel run interface."""
    def __init__(self, cmd):
	threading.Thread.__init__(self)        
	self.cmd = cmd
    def run(self):
    	x = self.cmd.pop(0)
	x(*self.cmd)


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
	"""

	def __init__(self, control, jobtag='default'):
		"""
			control
				The control file (pathname of)
			jobtag
				The job tag string (eg "default")
		"""
		self.autodir = os.environ['AUTODIR']
		self.bindir = self.autodir + '/bin'
		self.testdir = self.autodir + '/tests'
		self.profdir = self.autodir + '/profilers'

		self.tmpdir = self.autodir + '/tmp'
		if os.path.exists(self.tmpdir):
			system('rm -rf ' + self.tmpdir)
		os.mkdir(self.tmpdir)

		self.resultdir = self.autodir + '/results/' + jobtag
		if os.path.exists(self.resultdir):
			system('rm -rf ' + self.resultdir)
		os.mkdir(self.resultdir)

		os.mkdir(self.resultdir + "/debug")
		os.mkdir(self.resultdir + "/analysis")
		os.mkdir(self.resultdir + "/sysinfo")

		self.control = control
		self.jobtab = jobtag

		self.stdout = fd_stack(1, sys.stdout)
		self.stderr = fd_stack(2, sys.stderr)

		self.profilers = profilers.profilers(self)

		pwd = os.getcwd()	
		os.chdir(self.resultdir + "/sysinfo")
		system(self.bindir + '/sysinfo.py')
		os.chdir(pwd)

	def kernel(self, topdir, base_tree):
		"""Summon a kernel object"""
		return kernel.kernel(self, topdir, base_tree)

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


        def __runtest(self, tag, testname, test_args):
                try:
			test.runtest(self, tag, testname, test_args)
                except AutotestError:
                        raise
                except:
                        raise UnhandledError('running test ' + \
                                self.__class__.__name__ + "\n")

	def runtest(self, tag, testname, *test_args):
		"""Summon a test object and run it.
		
		tag
			tag to add to testname
		testname
			name of the test to run
		"""
		name = testname 
		if (tag):
			name += '.' + tag
		try:
			try:
				self.__runtest(tag, testname, test_args)
			except Exception, detail:
				self.record("FAIL " + name + " " + \
					detail.__str__() + "\n")

				raise
			else:
				self.record("GOOD " + name + \
					" Completed Successfully\n")
		except TestError:
			return 0
		except:
			raise
		else:
			return 1

	def noop(self, text):
		print "job: noop: " + text

	# Job control primatives.

	def parallel(self, *tasklist):
		"""Run tasks in parallel"""
		tasks = []
		for t in tasklist:
			task = AsyncRun(t)
			tasks.append(task)
			task.start()
		for t in tasks:
			t.join()

	def quit(self):
		# XXX: should have a better name.
		raise JobContinue("more to come")

	def complete(self, status):
		"""Clean up and exit"""
		# We are about to exit 'complete' so clean up the control file.
		try:
			os.unlink(self.control + '.state')
		except:
			pass
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

		# If there is a mid-job state file load that in and continue
		# where it indicates.  Otherwise start stepping at the passed
		# entry.
		try:
			self.steps = pickle.load(open(self.control + '.state',
				'r'))
		except:
			if lcl.has_key('step_init'):
				self.next_step([lcl['step_init']])

		# Run the step list.
		while len(self.steps) > 0:
			step = self.steps.pop(0)
			pickle.dump(self.steps, open(self.control + '.state',
				'w'))

			cmd = step.pop(0)
			cmd = lcl[cmd]
			lcl['__cmd'] = cmd
			lcl['__args'] = step
			exec("__cmd(*__args)", lcl, lcl)

		# all done, clean up and exit.
		self.complete(0)

	def record(self, msg):
		"""Record job-level status"""
		print msg
		status = self.resultdir + "/status"
		fd = file(status, "a")
		fd.write(msg)
		fd.close()


def runjob(control, cont = 0):
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
		if cont == 1 and not os.path.exists(state):
			sys.exit(1)
		if cont == 0 and os.path.exists(state):
			os.unlink(state)

		myjob = job(control)

		# Load in the users control file, may do any one of:
		#  1) execute in toto
		#  2) define steps, and select the first via next_step()
		myjob.step_engine()

		# If we get here, then we assume the job is complete and good.
		myjob.complete(0)

	except JobContinue:
		sys.exit(5)

	except JobError, instance:
		print "JOB ERROR: " + instance.args[0]
		if myjob != None:
			myjob.complete(1)

	except:
		# Ensure we cannot continue this job, it is in rictus.
		if os.path.exists(state):
			os.unlink(state)
		raise
