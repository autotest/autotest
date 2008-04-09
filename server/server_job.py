"""
The main job wrapper for the server side.

This is the core infrastructure. Derived from the client side job.py

Copyright Martin J. Bligh, Andy Whitcroft 2007
"""

__author__ = """
Martin J. Bligh <mbligh@google.com>
Andy Whitcroft <apw@shadowen.org>
"""

import os, sys, re, time, select, subprocess, traceback
import test
from utils import *
from common.error import *

# this magic incantation should give us access to a client library
server_dir = os.path.dirname(__file__)
client_dir = os.path.join(server_dir, "..", "client", "bin")
sys.path.append(client_dir)
import fd_stack
sys.path.pop()

# load up a control segment
# these are all stored in <server_dir>/control_segments
def load_control_segment(name):
	server_dir = os.path.dirname(os.path.abspath(__file__))
	script_file = os.path.join(server_dir, "control_segments", name)
	if os.path.exists(script_file):
		return file(script_file).read()
	else:
		return ""


preamble = """\
import os, sys

import hosts, autotest, kvm, git, standalone_profiler
import source_kernel, rpm_kernel, deb_kernel, git_kernel
from common.error import *
from common import barrier
from subcommand import *
from utils import run, get_tmp_dir, sh_escape

autotest.Autotest.job = job
hosts.SSHHost.job = job
barrier = barrier.barrier

if len(machines) > 1:
	open('.machines', 'w').write('\\n'.join(machines) + '\\n')
"""

client_wrapper = """
at = autotest.Autotest()

def run_client(machine):
	host = hosts.SSHHost(machine)
	at.run(control, host=host)

parallel_simple(run_client, machines)
"""

crashdumps = """
def crashdumps(machine):
	host = hosts.SSHHost(machine, initialize=False)
	host.get_crashdumps(test_start_time)

parallel_simple(crashdumps, machines, log=False)
"""

reboot_segment="""\
def reboot(machine):
	host = hosts.SSHHost(machine, initialize=False)
	host.reboot()

parallel_simple(reboot, machines, log=False)
"""

install="""\
def install(machine):
	host = hosts.SSHHost(machine, initialize=False)
	host.machine_install()

parallel_simple(install, machines, log=False)
"""

# load up the verifier control segment, with an optional site-specific hook
verify = load_control_segment("site_verify")
verify += load_control_segment("verify")

# load up the repair control segment, with an optional site-specific hook
repair = load_control_segment("site_repair")
repair += load_control_segment("repair")


# load up site-specific code for generating site-specific job data
try:
	import site_job
	get_site_job_data = site_job.get_site_job_data
	del site_job
except ImportError:
	# by default provide a stub that generates no site data
	def get_site_job_data(job):
		return {}


class base_server_job:
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

	def __init__(self, control, args, resultdir, label, user, machines,
								client = False):
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
		path = os.path.dirname(__file__)
		self.autodir = os.path.abspath(os.path.join(path, '..'))
		self.serverdir = os.path.join(self.autodir, 'server')
		self.testdir   = os.path.join(self.serverdir, 'tests')
		self.tmpdir    = os.path.join(self.serverdir, 'tmp')
		self.conmuxdir = os.path.join(self.autodir, 'conmux')
		self.clientdir = os.path.join(self.autodir, 'client')
		if control:
			self.control = open(control, 'r').read()
			self.control = re.sub('\r', '', self.control)
		else:
			self.control = None
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
		self.machines = machines
		self.client = client
		self.record_prefix = ''
		self.warning_loggers = set()

		self.stdout = fd_stack.fd_stack(1, sys.stdout)
		self.stderr = fd_stack.fd_stack(2, sys.stderr)

		if os.path.exists(self.status):
			os.unlink(self.status)
		job_data = { 'label' : label, 'user' : user,
					'hostname' : ','.join(machines) }
		job_data.update(get_site_job_data(self))
		write_keyval(self.resultdir, job_data)


	def verify(self):
		if not self.machines:
			raise AutoservError('No machines specified to verify')
		try:
			namespace = {'machines' : self.machines, 'job' : self}
			exec(preamble + verify, namespace, namespace)
		except Exception, e:
			msg = 'Verify failed\n' + str(e) + '\n' + format_error()
			self.record('ABORT', None, None, msg)
			raise


	def repair(self):
		if not self.machines:
			raise AutoservError('No machines specified to repair')
		namespace = {'machines' : self.machines, 'job' : self}
		# no matter what happens during repair, go on to try to reverify
		try:
			exec(preamble + repair, namespace, namespace)
		except Exception, exc:
			print 'Exception occured during repair'
			traceback.print_exc()
		self.verify()


	def enable_external_logging(self):
		"""Start or restart external logging mechanism.
		"""
		pass


	def disable_external_logging(self):
		""" Pause or stop external logging mechanism.
		"""
		pass


	def use_external_logging(self):
		"""Return True if external logging should be used.
		"""
		return False


	def run(self, reboot = False, install_before = False,
		install_after = False, collect_crashdumps = True,
		namespace = {}):
		# use a copy so changes don't affect the original dictionary
		namespace = namespace.copy()
		machines = self.machines

		self.aborted = False
		namespace['machines'] = machines
		namespace['args'] = self.args
		namespace['job'] = self
		test_start_time = int(time.time())

		os.chdir(self.resultdir)
		
		self.enable_external_logging()
		status_log = os.path.join(self.resultdir, 'status.log')
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
			if machines and collect_crashdumps:
				namespace['test_start_time'] = test_start_time
				exec(preamble + crashdumps,
				     namespace, namespace)
			self.disable_external_logging()
			if reboot and machines:
				exec(preamble + reboot_segment,
				     namespace, namespace)
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
			self.record('FAIL', subdir, testname, str(detail) + "\n" + format_error())


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


	def record(self, status_code, subdir, operation, status=''):
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

		Executing this method will trigger the logging of all new
		warnings to date from the various console loggers.
		"""
		# poll all our warning loggers for new warnings
		warnings = self._read_warnings()
		for timestamp, msg in warnings:
			self.__record("WARN", None, None, msg, timestamp)

		# write out the actual status log line
		self.__record(status_code, subdir, operation, status)


	def _read_warnings(self):
		warnings = []
		while True:
			# pull in a line of output from every logger that has
			# output ready to be read
			loggers, _, _ = select.select(self.warning_loggers,
						      [], [], 0)
			closed_loggers = set()
			for logger in loggers:
				line = logger.readline()
				# record any broken pipes (aka line == empty)
				if len(line) == 0:
					closed_loggers.add(logger)
					continue
				timestamp, msg = line.split('\t', 1)
				warnings.append((int(timestamp), msg.strip()))

			# stop listening to loggers that are closed
			self.warning_loggers -= closed_loggers

			# stop if none of the loggers have any output left
			if not loggers:
				break

		# sort into timestamp order
		warnings.sort()
		return warnings


	def _render_record(self, status_code, subdir, operation, status='',
			   epoch_time=None, record_prefix=None):
		"""
		Internal Function to generate a record to be written into a
		status log. For use by server_job.* classes only.
		"""
		if subdir:
			if re.match(r'[\n\t]', subdir):
				raise ValueError('Invalid character in subdir string')
			substr = subdir
		else:
			substr = '----'
		
		if not re.match(r'(START|(END )?(GOOD|WARN|FAIL|ABORT))$', \
								status_code):
			raise ValueError('Invalid status code supplied: %s' % status_code)
		if not operation:
			operation = '----'
		if re.match(r'[\n\t]', operation):
			raise ValueError('Invalid character in operation string')
		operation = operation.rstrip()
		status = status.rstrip()
		status = re.sub(r"\t", "  ", status)
		# Ensure any continuation lines are marked so we can
		# detect them in the status file to ensure it is parsable.
		status = re.sub(r"\n", "\n" + self.record_prefix + "  ", status)

		# Generate timestamps for inclusion in the logs
		if epoch_time is None:
			epoch_time = int(time.time())
		local_time = time.localtime(epoch_time)
		epoch_time_str = "timestamp=%d" % (epoch_time,)
		local_time_str = time.strftime("localtime=%b %d %H:%M:%S",
					       local_time)

		if record_prefix is None:
			record_prefix = self.record_prefix

		msg = '\t'.join(str(x) for x in (status_code, substr, operation,
						 epoch_time_str, local_time_str,
						 status))
		return record_prefix + msg + '\n'


	def _record_prerendered(self, msg):
		"""
		Record a pre-rendered msg into the status logs. The only
		change this makes to the message is to add on the local
		indentation. Should not be called outside of server_job.*
		classes. Unlike __record, this does not write the message
		to standard output.
		"""
		status_file = os.path.join(self.resultdir, 'status.log')
		status_log = open(status_file, 'a')
		need_reparse = False
		for line in msg.splitlines():
			line = self.record_prefix + line + '\n'
			status_log.write(line)
			if self.__need_reparse(line):
				need_reparse = True
		status_log.close()
		if need_reparse:
			self.__parse_status()


	def __record(self, status_code, subdir, operation, status='',
		     epoch_time=None):
		"""
		Actual function for recording a single line into the status
		logs. Should never be called directly, only by job.record as
		this would bypass the console monitor logging.
		"""

		msg = self._render_record(status_code, subdir, operation,
					  status, epoch_time)


		status_file = os.path.join(self.resultdir, 'status.log')
		sys.stdout.write(msg)
		open(status_file, "a").write(msg)
		if subdir:
			test_dir = os.path.join(self.resultdir, subdir)
			if not os.path.exists(test_dir):
				os.mkdir(test_dir)
			status_file = os.path.join(test_dir, 'status')
			open(status_file, "a").write(msg)
		if self.__need_reparse(msg):
			self.__parse_status()


	def __need_reparse(self, line):
		# the parser will not record results if lines have more than
		# one level of indentation
		indent = len(re.search(r"^(\t*)", line).group(1))
		if indent > 1:
			return False
		# we can also skip START lines, as they add nothing
		line = line.lstrip("\t")
		if line.startswith("START\t"):
			return False
		# otherwise, we should do a parse
		return True


	def __parse_status(self):
		"""
		If a .parse.cmd file is present in the results directory,
		launch the tko parser.
		"""
		cmdfile = os.path.join(self.resultdir, '.parse.cmd')
		if os.path.exists(cmdfile):
			cmd = open(cmdfile).read().strip()
			subprocess.Popen(cmd, shell=True)


# a file-like object for catching stderr from an autotest client and
# extracting status logs from it
class client_logger(object):
	"""Partial file object to write to both stdout and
	the status log file.  We only implement those methods
	utils.run() actually calls.
	"""
	parser = re.compile(r"^AUTOTEST_STATUS:([^:]*):(.*)$")
	extract_indent = re.compile(r"^(\t*).*$")

	def __init__(self, job):
		self.job = job
		self.leftover = ""
		self.last_line = ""
		self.logs = {}


	def _process_log_dict(self, log_dict):
		log_list = log_dict.pop("logs", [])
		for key in sorted(log_dict.iterkeys()):
			log_list += self._process_log_dict(log_dict.pop(key))
		return log_list


	def _process_logs(self):
		"""Go through the accumulated logs in self.log and print them
		out to stdout and the status log. Note that this processes
		logs in an ordering where:

		1) logs to different tags are never interleaved
		2) logs to x.y come before logs to x.y.z for all z
		3) logs to x.y come before x.z whenever y < z

		Note that this will in general not be the same as the
		chronological ordering of the logs. However, if a chronological
		ordering is desired that one can be reconstructed from the
		status log by looking at timestamp lines."""
		log_list = self._process_log_dict(self.logs)
		for line in log_list:
			self.job._record_prerendered(line + '\n')
		if log_list:
			self.last_line = log_list[-1]


	def _process_quoted_line(self, tag, line):
		"""Process a line quoted with an AUTOTEST_STATUS flag. If the
		tag is blank then we want to push out all the data we've been
		building up in self.logs, and then the newest line. If the
		tag is not blank, then push the line into the logs for handling
		later."""
		print line
		if tag == "":
			self._process_logs()
			self.job._record_prerendered(line + '\n')
			self.last_line = line
		else:
			tag_parts = [int(x) for x in tag.split(".")]
			log_dict = self.logs
			for part in tag_parts:
				log_dict = log_dict.setdefault(part, {})
			log_list = log_dict.setdefault("logs", [])
			log_list.append(line)


	def _process_line(self, line):
		"""Write out a line of data to the appropriate stream. Status
		lines sent by autotest will be prepended with
		"AUTOTEST_STATUS", and all other lines are ssh error
		messages."""
		match = self.parser.search(line)
		if match:
			tag, line = match.groups()
			self._process_quoted_line(tag, line)
		else:
			print line


	def _format_warnings(self, last_line, warnings):
		# use the indentation of whatever the last log line was
		indent = self.extract_indent.match(last_line).group(1)
		# if the last line starts a new group, add an extra indent
		if last_line.lstrip('\t').startswith("START\t"):
			indent += '\t'
		return [self.job._render_record("WARN", None, None, msg,
						timestamp, indent).rstrip('\n')
			for timestamp, msg in warnings]


	def _process_warnings(self, last_line, log_dict, warnings):
		if log_dict.keys() in ([], ["logs"]):
			# there are no sub-jobs, just append the warnings here
			warnings = self._format_warnings(last_line, warnings)
			log_list = log_dict.setdefault("logs", [])
			log_list += warnings
			for warning in warnings:
				sys.stdout.write(warning + '\n')
		else:
			# there are sub-jobs, so put the warnings in there
			log_list = log_dict.get("logs", [])
			if log_list:
				last_line = log_list[-1]
			for key in sorted(log_dict.iterkeys()):
				if key != "logs":
					self._process_warnings(last_line,
							       log_dict[key],
							       warnings)


	def write(self, data):
		# first check for any new console warnings
		warnings = self.job._read_warnings()
		self._process_warnings(self.last_line, self.logs, warnings)
		# now process the newest data written out
		data = self.leftover + data
		lines = data.split("\n")
		# process every line but the last one
		for line in lines[:-1]:
			self._process_line(line)
		# save the last line for later processing
		# since we may not have the whole line yet
		self.leftover = lines[-1]


	def flush(self):
		sys.stdout.flush()


	def close(self):
		if self.leftover:
			self._process_line(self.leftover)
		self._process_logs()
		self.flush()

# site_server_job.py may be non-existant or empty, make sure that an
# appropriate site_server_job class is created nevertheless
try:
	from site_server_job import site_server_job
except ImportError:
	class site_server_job(base_server_job):
		pass
	
class server_job(site_server_job):
	pass
