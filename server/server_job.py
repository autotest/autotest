"""
The main job wrapper for the server side.

This is the core infrastructure. Derived from the client side job.py

Copyright Martin J. Bligh, Andy Whitcroft 2007
"""

__author__ = """
Martin J. Bligh <mbligh@google.com>
Andy Whitcroft <apw@shadowen.org>
"""

import os, sys, re, time
import test
from utils import *
from error import *

# this magic incantation should give us access to a client library
server_dir = os.path.dirname(__file__)
client_dir = os.path.join(server_dir, "..", "client", "bin")
sys.path.append(client_dir)
import fd_stack
sys.path.pop()

preamble = """\
import os, sys
sys.stderr = __stderr

import errors, hosts, autotest, kvm
import source_kernel, rpm_kernel, deb_kernel
from subcommand import *
from utils import run, get_tmp_dir, sh_escape

"""

client_wrapper = """
at = autotest.Autotest()

def run_client(machine):
	host = hosts.SSHHost(machine)
	at.run(control, host=host)

if len(machines) > 1:
	open('.machines', 'w').write('\\n'.join(machines) + '\\n')
	parallel_simple(run_client, machines)
else:
	run_client(machines[0])
"""

crashdumps = """
def crashdumps(machine):
	host = hosts.SSHHost(machine, initialize=False)
	host.get_crashdumps(test_start_time)

parallel_simple(crashdumps, machines, log=False)
"""

cleanup="""\
def cleanup(machine):
		host = hosts.SSHHost(machine, initialize=False)
		host.reboot()

parallel_simple(cleanup, machines, log=False)
"""

install="""\
def install(machine):
		host = hosts.SSHHost(machine, initialize=False)
		host.machine_install()

parallel_simple(cleanup, machines, log=False)
"""

class server_job:
	"""The actual job against which we do everything.

	Properties:
		autodir
			The top level autotest directory (/usr/local/autotest).
		serverdir
			<autodir>/server/
		clientdir
			<autodir>/client/
		conmuxdir
			<autodir>/conmux/
		testdir
			<autodir>/server/tests/
		control
			the control file for this job
	"""

	def __init__(self, control, args, resultdir, label, user, client=False):
		"""
			control
				The control file (pathname of)
			args
				args to pass to the control file
			resultdir
				where to throw the results
			label
				label for the job
			user	
				Username for the job (email address)
			client
				True if a client-side control file
		"""
		path = os.path.dirname(sys.modules['server_job'].__file__)
		self.autodir = os.path.abspath(os.path.join(path, '..'))
		self.serverdir = os.path.join(self.autodir, 'server')
		self.testdir   = os.path.join(self.serverdir, 'tests')
		self.tmpdir    = os.path.join(self.serverdir, 'tmp')
		self.conmuxdir = os.path.join(self.autodir, 'conmux')
		self.clientdir = os.path.join(self.autodir, 'client')
		self.control = re.sub('\r\n', '\n', open(control, 'r').read())
		self.resultdir = resultdir
		if not os.path.exists(resultdir):
			os.mkdir(resultdir)
		self.debugdir = os.path.join(resultdir, 'debug')
		if not os.path.exists(self.debugdir):
			os.mkdir(self.debugdir)
		self.status = os.path.join(resultdir, 'status')
		self.label = label
		self.user = user
		self.args = args
		self.client = client
		self.record_prefix = ''

		self.stdout = fd_stack.fd_stack(1, sys.stdout)
		self.stderr = fd_stack.fd_stack(2, sys.stderr)

		if os.path.exists(self.status):
			os.unlink(self.status)
		job_data = { 'label' : label, 'user' : user}
		write_keyval(self.resultdir, job_data)


	def run(self, machines, reboot = False, install_before = False,
					install_after = False, namespace = {}):
		# use a copy so changes don't affect the original dictionary
		namespace = namespace.copy()

		namespace['machines'] = machines
		namespace['args'] = self.args
		namespace['job'] = self
		test_start_time = int(time.time())

		os.chdir(self.resultdir)

		status_log = os.path.join(self.resultdir, 'status.log')
		namespace['__stderr'] = open(status_log, 'a', 0)
		try:
			if install_before and machines:
				exec(preamble + install, namespace, namespace)
			if self.client:
				namespace['control'] = self.control
				open('control', 'w').write(self.control)
				open('control.srv', 'w').write(client_wrapper)
				server_control = client_wrapper
			else:
				open('control.srv', 'w').write(self.control)
				server_control = self.control
			exec(preamble + server_control, namespace, namespace)

		finally:
			if machines:
				namespace['test_start_time'] = test_start_time
				exec(preamble + crashdumps, namespace,
					namespace)
			if reboot and machines:
				exec(preamble + cleanup, namespace, namespace)
			if install_after and machines:
				exec(preamble + install, namespace, namespace)


	def run_test(self, url, *args, **dargs):
		"""Summon a test object and run it.
		
		tag
			tag to add to testname
		url
			url of the test to run
		"""

		(group, testname) = test.testname(url)
		tag = None
		subdir = testname

		if dargs.has_key('tag'):
			tag = dargs['tag']
			del dargs['tag']
			if tag:
				subdir += '.' + tag

		try:
			test.runtest(self, url, tag, args, dargs)
			self.record('GOOD', subdir, testname, 'completed successfully')
		except Exception, detail:
			self.record('FAIL', subdir, testname, format_error())


	def run_group(self, function, *args, **dargs):
		"""\
		function:
			subroutine to run
		*args:
			arguments for the function
		"""

		result = None
		name = function.__name__

		# Allow the tag for the group to be specified.
		if dargs.has_key('tag'):
			tag = dargs['tag']
			del dargs['tag']
			if tag:
				name = tag

		# if tag:
		#	name += '.' + tag
		old_record_prefix = self.record_prefix
		try:
			try:
				self.record('START', None, name)
				self.record_prefix += '\t'
				result = function(*args, **dargs)
				self.record_prefix = old_record_prefix
				self.record('END GOOD', None, name)
			except:
				self.record_prefix = old_record_prefix
				self.record('END FAIL', None, name, format_error())
		# We don't want to raise up an error higher if it's just
		# a TestError - we want to carry on to other tests. Hence
		# this outer try/except block.
		except TestError:
			pass
		except:
			raise TestError(name + ' failed\n' + format_error())

		return result


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
		governed by self.record_prefix

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
		if re.match(r'[\n\t]', operation):
			raise "Invalid character in operation string"
		operation = operation.rstrip()
		status = status.rstrip()
		status = re.sub(r"\t", "  ", status)
		# Ensure any continuation lines are marked so we can
		# detect them in the status file to ensure it is parsable.
		status = re.sub(r"\n", "\n" + self.record_prefix + "  ", status)

		msg = '%s\t%s\t%s\t%s' %(status_code, substr, operation, status)

		status_file = os.path.join(self.resultdir, 'status')
		print msg
		open(status_file, "a").write(self.record_prefix + msg + "\n")
		if subdir:
			status_file = os.path.join(self.resultdir, subdir, 'status')
			open(status_file, "a").write(msg + "\n")
