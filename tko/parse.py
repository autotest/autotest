#!/usr/bin/python
import os, re, md5

valid_users = r'(apw|mbligh|andyw|korgtest)'
build_stock = re.compile('build generic stock (2\.\S+)')	
build_url   = re.compile('build generic url \S*/linux-(2\.\d\.\d+(\.\d+)?(-rc\d+)?).tar')	
valid_kernel= re.compile('2\.\d\.\d+(\.\d+)?(-rc\d+)?(-(git|bk))\d+')

def shorten_patch(long):
	short = os.path.basename(long)
	short = re.sub(r'^patch-', '', short)
	short = re.sub(r'\.(bz2|gz)$', '', short)
	short = re.sub(r'\.patch$', '', short)
	short = re.sub(r'\+', '_', short)
	return short


class job:
	def __init__(self, dir, type):
		self.dir = dir
		self.type = type
		self.control = os.path.join(dir, "control")
		self.status = os.path.join(dir, "status")
		self.variables = {}
		self.tests = []
		self.kernel = None

		if not os.path.exists(self.status):
			return None

		# We should really replace this with sysinfo/hostname!
		uname = os.path.join(dir, "sysinfo/uname_-a")
		try:
			self.machine = open(uname, 'r').readline().split()[1]
		except:
			return None

		self.grope_status()


	def grope_status(self):
		# HACK. we don't have proper build tags in the status file yet
		# so we hardcode build/ and do it at the start of the job
		build = os.path.join(self.dir, 'build')
		if os.path.exists(build):
			self.kernel = kernel(build)

		for line in open(self.status, 'r').readlines():
			(status, testname, reason) = line.rstrip().split(' ', 2)
			print 'GROPE_STATUS: ',
			print (status, testname, reason)

		self.tests.append(test(testname, status, reason, self.kernel, self))


class kernel:
	def __init__(self, builddir):
		self.base = None
		self.patches = []

		log = os.path.join(builddir, 'debug/build_log')
		if not os.path.exists(log):
			return
		patch_hashes = []
		for line in open(log, 'r'):
			print line
			(type, rest) = line.split(': ', 1)
			words = rest.split()
			if type == 'BUILD VERSION':
				self.base = words[0]
			if type == 'PATCH':
				print words
				self.patches.append(patch(*words[0:]))
				# patch_hashes.append(words[2])
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
	def __init__(self, dir, status, reason, kernel, job):
		self.dir = dir
		self.status = status
		self.reason = reason
		self.keyval = os.path.join(dir, 'results/keyval')
		self.iterations = []
		self.testname = re.sub(r'\..*', '', self.dir)
		self.kernel = kernel
		self.machine = job.machine

		if not os.path.exists(self.keyval):
			self.keyval = None
			return
		count = 1
		lines = []
		for line in open(self.keyval, 'r').readlines():
			if not re.search('\S'):			# blank line
				self.iterations.append(iteration(count, lines))
				lines = []
				count += 1
				next
			else:
				lines.append(line)
		if lines:
			self.iterations.append(iteration(count, lines))


class iteration:
	def __init__(self, index, lines):
		self.index = index
		self.keyval = {}

		for line in lines:
			(key, value) = line.split('=', 1)
			self.keyval[key] = value
