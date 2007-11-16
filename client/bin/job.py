"""The main job wrapper

This is the core infrastructure.
"""

__author__ = """Copyright Andy Whitcroft, Martin J. Bligh 2006"""

# standard stuff
import os, sys, re, pickle, shutil, time, traceback
# autotest stuff
from autotest_utils import *
from parallel import *
from error import *
import kernel, xen, test, profilers, barrier, filesystem, fd_stack, boottool
import harness, config
import sysinfo

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

	def __init__(self, control, jobtag, cont, harness_type=None):
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
		self.bindir = os.path.join(self.autodir, 'bin')
		self.testdir = os.path.join(self.autodir, 'tests')
		self.profdir = os.path.join(self.autodir, 'profilers')
		self.tmpdir = os.path.join(self.autodir, 'tmp')
		self.resultdir = os.path.join(self.autodir, 'results', jobtag)

		if not cont:
			if os.path.exists(self.tmpdir):
				system('umount -f %s > /dev/null 2> /dev/null'%\
					 	self.tmpdir, ignorestatus=True)
				system('rm -rf ' + self.tmpdir)
			os.mkdir(self.tmpdir)

			results = os.path.join(self.autodir, 'results')
			if not os.path.exists(results):
				os.mkdir(results)
				
			download = os.path.join(self.testdir, 'download')
			if os.path.exists(download):
				system('rm -rf ' + download)
			os.mkdir(download)
				
			if os.path.exists(self.resultdir):
				system('rm -rf ' + self.resultdir)
			os.mkdir(self.resultdir)

			os.mkdir(os.path.join(self.resultdir, 'debug'))
			os.mkdir(os.path.join(self.resultdir, 'analysis'))
			os.mkdir(os.path.join(self.resultdir, 'sysinfo'))

			shutil.copyfile(control, os.path.join(self.resultdir, 'control'))

		self.control = control
		self.jobtag = jobtag

		self.stdout = fd_stack.fd_stack(1, sys.stdout)
		self.stderr = fd_stack.fd_stack(2, sys.stderr)
		self.group_level = 0

		self.config = config.config(self)

		self.harness = harness.select(harness_type, self)

		self.profilers = profilers.profilers(self)

		try:
			tool = self.config_get('boottool.executable')
			self.bootloader = boottool.boottool(tool)
		except:
			pass

		# log "before each step" sysinfo
		pwd = os.getcwd()
		try:
			os.chdir(os.path.join(self.resultdir, 'sysinfo'))
			sysinfo.before_each_step()
		finally:
			os.chdir(pwd)

		if not cont:
			self.record('START', None, None)
			self.harness.run_start()
		self.group_level = 1


	def relative_path(self, path):
		"""\
		Return a patch relative to the job results directory
		"""
		head = len(self.resultdir) + 1     # remove the / inbetween
		return path[head:]


	def control_get(self):
		return self.control


	def harness_select(self, which):
		self.harness = harness.select(which, self)


	def config_set(self, name, value):
		self.config.set(name, value)


	def config_get(self, name):
		return self.config.get(name)

	def setup_dirs(self, results_dir, tmp_dir):
		if not tmp_dir:
			tmp_dir = os.path.join(self.tmpdir, 'build')
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
		return kernel.auto_kernel(self, base_tree, results_dir,
					  tmp_dir, build_dir, leave)


	def barrier(self, *args):
		"""Create a barrier object"""
		return barrier.barrier(*args)


	def setup_dep(self, deps): 
		"""Set up the dependencies for this test.
		
		deps is a list of libraries required for this test.
		"""
		for dep in deps: 
			try: 
				os.chdir(os.path.join(self.autodir, 'deps', dep))
				system('./' + dep + '.py')
			except: 
				error = "setting up dependency " + dep + "\n"
				raise UnhandledError(error)


	def __runtest(self, url, tag, args, dargs):
		try:
			l = lambda : test.runtest(self, url, tag, args, dargs)
			pid = fork_start(self.resultdir, l)
			fork_waitfor(self.resultdir, pid)
		except AutotestError:
			raise
		except:
			raise UnhandledError('running test ' + \
				self.__class__.__name__ + "\n")


	def run_test(self, url, *args, **dargs):
		"""Summon a test object and run it.
		
		tag
			tag to add to testname
		url
			url of the test to run
		"""

		if not url:
			raise "Test name is invalid. Switched arguments?"
		(group, testname) = test.testname(url)
		tag = dargs.pop('tag', None)
		subdir = testname
		if tag:
			subdir += '.' + tag

		def group_func():
			try:
				self.__runtest(url, tag, args, dargs)
			except Exception, detail:
				self.record('FAIL', subdir, testname,
					    str(detail))
				raise
			else:
				self.record('GOOD', subdir, testname,
					    'completed successfully')
		name = "test." + testname
		result, exc_info = self.__rungroup(name, group_func)

		if exc_info and isinstance(exc_info[1], TestError):
			return False
		elif exc_info:
			raise exc_info[0], exc_info[1], exc_info[2]
		else:
			return True


	def __rungroup(self, name, function, *args, **dargs):
		"""\
		name:
		        name of the group
		function:
			subroutine to run
		*args:
			arguments for the function

		Returns a 2-tuple (result, exc_info) where result
		is the return value of function, and exc_info is
		the sys.exc_info() of the exception thrown by the
		function (which may be None).
		"""

		result, exc_info = None, None
		try:
			self.record('START', None, name)
			self.group_level += 1
			result = function(*args, **dargs)
			self.group_level -= 1
			self.record('END GOOD', None, name)
		except Exception, e:
			exc_info = sys.exc_info()
			self.group_level -= 1
			self.record('END FAIL', None, name, format_error())

		return result, exc_info


	def run_group(self, function, *args, **dargs):
		"""\
		function:
			subroutine to run
		*args:
			arguments for the function
		"""

		# Allow the tag for the group to be specified
		name = function.__name__
		tag = dargs.pop('tag', None)
		if tag:
			name = tag

		result, exc_info = self.__rungroup(name, function,
						   *args, **dargs)

		# if there was a non-TestError exception, raise it
		if exc_info and isinstance(exc_info[1], TestError):
			err = ''.join(traceback.format_exception(*exc_info))
			raise TestError(name + ' failed\n' + err)

		# pass back the actual return value from the function
		return result


	# Check the passed kernel identifier against the command line
	# and the running kernel, abort the job on missmatch.
	def kernel_check_ident(self, expected_when, expected_id, expected_cl, subdir, type = 'src'):
		print "POST BOOT: checking booted kernel mark=%d identity='%s' changelist=%s type='%s'" \
			% (expected_when, expected_id, expected_cl, type)

		running_id = running_os_ident()

		cmdline = read_one_line("/proc/cmdline")

		find_sum = re.compile(r'.*IDENT=(\d+)')
		m = find_sum.match(cmdline)
		cmdline_when = -1
		if m:
			cmdline_when = int(m.groups()[0])

		cl_re = re.compile(r'\d{7,}')
		cl_match = cl_re.search(system_output('uname -v').split()[1])
		if cl_match:
			current_cl = cl_match.group()
		else:
			current_cl = None

		# We have all the facts, see if they indicate we
		# booted the requested kernel or not.
		bad = False
		if (type == 'src' and expected_id != running_id or
		    type == 'rpm' and not running_id.startswith(expected_id + '::')):
			print "check_kernel_ident: kernel identifier mismatch"
			bad = True
		if expected_when != cmdline_when:
			print "check_kernel_ident: kernel command line mismatch"
			bad = True
		if expected_cl and current_cl and str(expected_cl) != current_cl:
			print 'check_kernel_ident: kernel changelist mismatch'
			bad = True

		if bad:
			print "   Expected Ident: " + expected_id
			print "    Running Ident: " + running_id
			print "    Expected Mark: %d" % (expected_when)
			print "Command Line Mark: %d" % (cmdline_when)
			print "   Expected P4 CL: %s" % expected_cl
			print "            P4 CL: %s" % current_cl
			print "     Command Line: " + cmdline

			raise JobError("boot failure", "reboot.verify")

		self.record('GOOD', subdir, 'reboot.verify')


	def filesystem(self, device, mountpoint = None, loop_size = 0):
		if not mountpoint:
			mountpoint = self.tmpdir
		return filesystem.filesystem(self, device, mountpoint,loop_size)


	def reboot(self, tag='autotest'):
		self.record('GOOD', None, 'reboot.start')
		self.harness.run_reboot()
		default = self.config_get('boot.set_default')
		if default:
			self.bootloader.set_default(tag)
		else:
			self.bootloader.boot_once(tag)
		system("(sleep 5; reboot) </dev/null >/dev/null 2>&1 &")
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
		if not isinstance(step[0], basestring):
			step[0] = step[0].__name__
		self.steps.append(step)
		pickle.dump(self.steps, open(self.control + '.state', 'w'))


	def next_step_prepend(self, step):
		"""Insert a new step, executing first"""
		if not isinstance(step[0], basestring):
			step[0] = step[0].__name__
		self.steps.insert(0, step)
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
			lcl['__args'] = step
			exec(cmd + "(*__args)", lcl, lcl)


	def record(self, status_code, subdir, operation, status = ''):
		"""
		Record job-level status

		The intent is to make this file both machine parseable and
		human readable. That involves a little more complexity, but
		really isn't all that bad ;-)

		Format is <status code>\t<subdir>\t<operation>\t<status>

		status code: (GOOD|WARN|FAIL|ABORT)
			or   START
			or   END (GOOD|WARN|FAIL|ABORT)

		subdir: MUST be a relevant subdirectory in the results,
		or None, which will be represented as '----'

		operation: description of what you ran (e.g. "dbench", or
						"mkfs -t foobar /dev/sda9")

		status: error message or "completed sucessfully"

		------------------------------------------------------------

		Initial tabs indicate indent levels for grouping, and is
		governed by self.group_level

		multiline messages have secondary lines prefaced by a double
		space ('  ')
		"""

		if subdir:
			if re.match(r'[\n\t]', subdir):
				raise "Invalid character in subdir string"
			substr = subdir
		else:
			substr = '----'
		
		if not re.match(r'(START|(END )?(GOOD|WARN|FAIL|ABORT))$', \
								status_code):
			raise "Invalid status code supplied: %s" % status_code
		if not operation:
			operation = '----'
		if re.match(r'[\n\t]', operation):
			raise "Invalid character in operation string"
		operation = operation.rstrip()
		status = status.rstrip()
		status = re.sub(r"\t", "  ", status)
		# Ensure any continuation lines are marked so we can
		# detect them in the status file to ensure it is parsable.
		status = re.sub(r"\n", "\n" + "\t" * self.group_level + "  ", status)

		# Generate timestamps for inclusion in the logs
		epoch_time = int(time.time())  # seconds since epoch, in UTC
		local_time = time.localtime(epoch_time)
		epoch_time_str = "timestamp=%d" % (epoch_time,)
		local_time_str = time.strftime("localtime=%b %d %H:%M:%S",
					       local_time)

		msg = '\t'.join(str(x) for x in (status_code, substr, operation,
						 epoch_time_str, local_time_str,
						 status))
		msg = '\t' * self.group_level + msg

		self.harness.test_status_detail(status_code, substr,
							operation, status)
		self.harness.test_status(msg)
		print msg
		status_file = os.path.join(self.resultdir, 'status')
		open(status_file, "a").write(msg + "\n")
		if subdir:
			status_file = os.path.join(self.resultdir, subdir, 'status')
			open(status_file, "a").write(msg + "\n")


def runjob(control, cont = False, tag = "default", harness_type = ''):
	"""The main interface to this module

	control
		The control file to use for this job.
	cont
		Whether this is the continuation of a previously started job
	"""
	control = os.path.abspath(control)
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
		if myjob:
			command = None
			if len(instance.args) > 1:
				command = instance.args[1]
			myjob.group_level = 0
			myjob.record('ABORT', None, command, instance.args[0])
			myjob.record('END ABORT', None, None)
			myjob.complete(1)

	except Exception, e:
		msg = format_error()
		print "JOB ERROR: " + msg
		if myjob:
			myjob.group_level = 0
			myjob.record('ABORT', None, None, msg)
			myjob.record('END ABORT', None, None)
			myjob.complete(1)

	# If we get here, then we assume the job is complete and good.
	myjob.group_level = 0
	myjob.record('END GOOD', None, None)
	myjob.complete(0)
