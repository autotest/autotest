#!/usr/bin/python
import os, re, md5, sys, email.Message, smtplib, datetime

client_bin = os.path.join(os.path.dirname(__file__), '../client/bin')
sys.path.insert(0, os.path.abspath(client_bin))
from autotest_utils import read_keyval

user = re.compile(r'user(\s*)=')
label = re.compile(r'label(\s*)=')

debug = True

# XXX: these mail bits came almost verbatim from mirror/mirror and this should
# probably be refactored into another file and used by both.
def mail(from_address, to_addresses, cc_addresses, subject, message_text):
	# if passed a string for the to_addresses convert it to a tuple
	if type(to_addresses) is str:
		to_addresses = (to_addresses,)

	message = email.Message.Message()
	message["To"] = ", ".join(to_addresses)
	message["Cc"] = ", ".join(cc_addresses)
	message["From"] = from_address
	message["Subject"] = subject
	message.set_payload(message_text)

	try:
		sendmail(message.as_string())
	except SendmailException, e:
		server = smtplib.SMTP("localhost")
		server.sendmail(from_address, to_addresses, cc_addresses, message.as_string())
		server.quit()


MAIL = "sendmail"

class SendmailException(Exception):
	pass

def sendmail(message):
	"""Send an email using sendmail"""
	# open a pipe to the mail program and
	# write the data to the pipe
	p = os.popen("%s -t" % MAIL, 'w')
	p.write(message)
	exitcode = p.close()
	if exitcode:
		raise SendmailException("Exit code: %s" % exitcode)

# XXX: End of code from mirror/mirror


def shorten_patch(long):
	short = os.path.basename(long)
	short = re.sub(r'^patch-', '', short)
	short = re.sub(r'\.(bz2|gz)$', '', short)
	short = re.sub(r'\.patch$', '', short)
	short = re.sub(r'\+', '_', short)
	return short


def dprint(info):
	if debug:
		sys.stderr.write(str(info) + '\n')


def get_timestamp(mapping, field):
	val = mapping.get(field, None)
	if val is not None:
		val = datetime.datetime.fromtimestamp(int(val))
	return val


class job:
	def __init__(self, dir):
		self.dir = dir
		self.control = os.path.join(dir, "control")
		self.status = os.path.join(dir, "status.log")
		if not os.path.exists(self.status):
			self.status = os.path.join(dir, "status")
		self.variables = {}
		self.tests = []
		self.kernel = None

		# Get the user + tag info from the keyval file.
		try:
			keyval = read_keyval(dir)
			print keyval
		except:
			keyval = {}
		self.user = keyval.get('user', None)
		self.label = keyval.get('label', None)
		self.machine = keyval.get('hostname', None)
		if self.machine:
			assert ',' not in self.machine
		self.queued_time = get_timestamp(keyval, 'job_queued')
		self.started_time = get_timestamp(keyval, 'job_started')
		self.finished_time = get_timestamp(keyval, 'job_finished')
		self.machine_owner = keyval.get('owner', None)

		if not self.machine:
			self.get_machine()

		print 'MACHINE NAME: ' + self.machine
		if not os.path.exists(self.status):
			return None

		self.grope_status()


	def get_machine(self):
		try:
			hostname = os.path.join(self.dir, "sysinfo/hostname")
			self.machine = open(hostname, 'r').readline().rstrip()
			return
		except:
			pass
		try:
			uname = os.path.join(self.dir, "sysinfo/uname_-a")
			self.machine = open(uname, 'r').readline().split()[1]
			return
		except:
			pass
		raise "Could not figure out machine name"
		

	def grope_status(self):
		"""
		Note that what we're looking for here is level 1 groups
		(ie end markers with 1 tab in front)

		For back-compatiblity, we also count level 0 groups that
		are not job-level events, if there's no start/end job level
		markers: "START   ----    ----"
		"""
		dprint('=====================================================')
		dprint(self.dir)
		dprint('=====================================================')
		self.kernel = kernel(self.dir)

		statuses = ['NOSTATUS', 'ERROR', 'ABORT', 'FAIL', 'WARN',
								'GOOD', 'ALERT']
		reboot_inprogress = 0	# Saw reboot start and not finish
		boot_count = 0
		alert_pending = None	# Saw an ALERT for this test
		group_subdir = None
		sought_level = 0        # we log events at indent level 0
		for line in open(self.status, 'r').readlines():
			dprint('\nSTATUS: ' + line.rstrip())
			if not re.search(r'^\t*\S', line):
				dprint('Continuation line, ignoring')
				continue	# ignore continuation lines
			if re.search(r'^START\t----\t----', line):
				sought_level = 1
				# we now log events at indent level 1
				dprint('Found job level start marker. Looking for level 1 groups now')
				continue
			indent = re.search('^(\t*)', line).group(0).count('\t')
			line = line.lstrip()
			line = line.rstrip('\n')
			if line.startswith('START\t'):
				group_subdir = None
				dprint('start line, ignoring')
				continue	# ignore start lines
			reason = None
			if line.startswith('END '):
				elements = line.split('\t')
				elements[0] = elements[0][4:] # remove 'END '
				end = True
			else:
				elements = line.split('\t')
				end = False
			(status, subdir, testname, reason) = elements[0:4]
			status, subdir, testname = elements[:3]
			reason = elements[-1]
			optional_fields = dict(element.split('=', 1)
					       for element in elements[3:-1])
			dprint('GROPE_STATUS: ' +
			       str([status, subdir, testname, reason]))
			if status == 'ALERT':
				dprint('job level alert, recording')
				alert_pending = reason
				continue
			if testname == 'Autotest.install' and status == 'GOOD':
				dprint('Sucessful autotest install, ignoring')
				continue
			if testname == '----':
				if status == 'ABORT' and not end:
					testname = 'JOB'
				else:
					dprint('job level event, ignoring')
					# This is a job level event, not a test
					continue
			################################################
			# REMOVE THIS SECTION ONCE OLD FORMAT JOBS ARE GONE
			################################################
			if re.search(r'^(GOOD|FAIL|WARN) ', line):
				(status, testname, reason) = line.split(None, 2)
				if testname.startswith('kernel.'):
					subdir = 'build'
				else:
					subdir = testname
			if testname.startswith('completed'):
				raise 'testname is crap'
			################################################
			if subdir == '----':
				subdir = None
			if line.startswith('END'):
				subdir = group_subdir
			if indent != sought_level and status != 'ABORT':
				# we're in a block group
				if subdir:
					dprint('set group_subdir: %s' % subdir)
					group_subdir = subdir
				dprint('incorrect indent level %d != %d, ignoring' % (indent, sought_level))
				continue
			if not re.search(r'^(boot$|kernel\.)', testname):
				# This is a real test
				if subdir and subdir.count('.'):
					# eg dbench.ext3
					testname = subdir
			if testname == 'reboot.start':
				dprint('reboot start event, ignoring')
				reboot_inprogress = 1
				continue
			if testname == 'reboot.verify':
				testname = 'boot.%d' % boot_count
				dprint('reboot verified')
				reboot_inprogress = 0
				boot_count += 1
			if alert_pending:
				status = 'ALERT'
				reason = alert_pending
				alert_pending = None
			if status in statuses:
				dprint('Adding: %s\nSubdir:%s\nTestname:%s\n%s'%
					(status, subdir, testname, reason))
			else:
				dprint('WARNING: Invalid status code. Ignoring')
				continue

			finished_time = get_timestamp(optional_fields,
						      'timestamp')
			self.tests.append(test(subdir, testname, status,
					       reason, self.kernel, self,
					       finished_time))
			dprint('')

		if reboot_inprogress:
			testname = 'boot.%d' % boot_count
			dprint('Adding: %s\nSubdir:%s\nTestname:%s\n%s' %
					('----', subdir, testname, reason))
			self.tests.append(test('----', testname, 'ABORT', 
				'machine did not return from reboot',
				self.kernel, self))
			dprint('')


class kernel:
	def __init__(self, topdir):
		self.base = 'UNKNOWN'
		self.patches = []
		patch_hashes = []
		# HACK. we don't have proper build tags in the status file yet
		# so we hardcode build/ and do it at the start of the job
		build_log = os.path.join(topdir, 'build/debug/build_log')

		if os.path.exists(build_log):
			for line in open(build_log, 'r'):
				print line
				(type, rest) = line.split(': ', 1)
				words = rest.split()
				if type == 'BASE':
					self.base = words[0]
				if type == 'PATCH':
					print words
					self.patches.append(patch(*words[0:]))
					patch_hashes.append(words[2])
		else:
			for sysinfo in ['sysinfo/reboot1', 'sysinfo']:
				uname_file = os.path.join(topdir, sysinfo, 'uname_-a')
				if not os.path.exists(uname_file):
					continue
				uname = open(uname_file, 'r').readline().split()
				self.base = uname[2]
				re.sub(r'-autotest$', '', self.base)
				break
		print 'kernel.__init__() found kernel version %s' % self.base
		if self.base == 'UNKNOWN':
			self.kernel_hash = 'UNKNOWN'
		else:
			self.kernel_hash = self.get_kver_hash(self.base, patch_hashes)


	def get_kver_hash(self, base, patch_hashes):
		"""\
		Calculate a hash representing the unique combination of
		the kernel base version plus 
		"""
		key_string = ','.join([base] + patch_hashes)
		return md5.new(key_string).hexdigest()


class patch:
	def __init__(self, spec, reference=None, hash=None):
		# NEITHER OF THE ABOVE SHOULD HAVE DEFAULTS!!!! HACK HACK
		if not reference:
			reference = spec
		print 'PATCH::%s %s %s' % (spec, reference, hash)
		self.spec = spec
		self.reference = reference
		self.hash = hash


class test:
	def __init__(self, subdir, testname, status, reason, kernel, job,
		     finished_time=None):
		# NOTE: subdir may be none here for lines that aren't an
		# actual test
		self.subdir = subdir
		self.testname = testname
		self.status = status
		self.reason = reason
		self.version = None
		self.keyval = None

		if subdir:
			keyval = os.path.join(job.dir, subdir, 'results/keyval')
			if os.path.exists(keyval):
				self.keyval = keyval
			keyval2 = os.path.join(job.dir, subdir, 'keyval')
			if os.path.exists(keyval2):
				self.version = open(keyval2, 'r').readline().split('=')[1]
		else:
			self.keyval = None
		self.iterations = []
		self.kernel = kernel
		self.machine = job.machine
		self.finished_time = finished_time

		dprint("PARSING TEST %s %s %s" % (subdir, testname, self.keyval))

		if not self.keyval:
			return
		count = 1
		lines = []
		for line in open(self.keyval, 'r').readlines():
			if not re.search('\S', line):		# blank line
				self.iterations.append(iteration(count, lines))
				lines = []
				count += 1
			else:
				lines.append(line)
		if lines:
			self.iterations.append(iteration(count, lines))


class iteration:
	def __init__(self, index, lines):
		self.index = index
		self.keyval = {}

		dprint("ADDING ITERATION %d" % index)
		for line in lines:
			line = line.rstrip();
			(key, value) = line.split('=', 1)
			self.keyval[key] = value
