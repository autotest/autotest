# Copyright Andy Whitcroft, Martin J. Bligh 2006

# The class describing a job
#
# Methods:
#	__init__	Initialize the job object
#	kernel		Summon a kernel object
#	runtest		Summon a test object and run it
#	parallel	Run tasks in parallel
#	complete	Clean up and exit
#	next_step	Define the next step
#	step_engine	Do the next step
#	record		Record job-level status
#
# Data:
#	autodir		The top level autotest directory (/usr/local/autotest)
#	bindir		bin/
#	testdir		tests/
#	profdir		profilers/
#	tmpdir		tmp/
#	resultdir	results/<jobtag>
#	control		The control file (pathname of)
#	jobtag		The job tag string (eg "default")
#
#	stdout		fd_stack object for stdout
#	stderr		fd_stack object for stderr
#	profilers	the profilers object for this job

from autotest_utils import *
import os, sys, kernel, test, pickle, threading, profilers

# Parallel run interface.
class AsyncRun(threading.Thread):
    def __init__(self, cmd):
	threading.Thread.__init__(self)        
	self.cmd = cmd
    def run(self):
    	x = self.cmd.pop(0)
	x(*self.cmd)

# JOB: the actual job against which we do everything.
class job:
	def __init__(self, control, jobtag='default'):
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
		return kernel.kernel(self, topdir, base_tree)

        def __runtest(self, tag, testname, test_args):
                try:
			test.runtest(self, tag, testname, test_args)
                except AutotestError:
                        raise
                except:
                        raise UnhandledError('running test ' + \
                                self.__class__.__name__ + "\n")

	def runtest(self, tag, testname, *test_args):
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
	def parallel(self, *l):
		tasks = []
		for t in l:
			task = AsyncRun(t)
			tasks.append(task)
			task.start()
		for t in tasks:
			t.join()

	# XXX: should have a better name.
	def quit(self):
		raise JobContinue("more to come")

	def complete(self, status):
		# We are about to exit 'complete' so clean up the control file.
		try:
			os.unlink(self.control + '.state')
		except:
			pass
		sys.exit(status)

	# STEPS: the stepping engine -- if the control file defines
	#        step_init we will be using this engine to drive multiple
	#        runs.
	steps = []
	def next_step(self, step):
		step[0] = step[0].__name__
		self.steps.append(step)
		pickle.dump(self.steps, open(self.control + '.state', 'w'))

	def step_engine(self):
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
		print msg
		status = self.resultdir + "/status"
		fd = file(status, "a")
		fd.write(msg)
		fd.close()


def runjob(control, cont = 0):
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
