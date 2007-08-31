#!/usr/bin/python
import os, re, md5

valid_users = r'(apw|mbligh|andyw|korgtest)'
build_stock = re.compile('build generic stock (2\.\S+)')	
build_url   = re.compile('build generic url \S*/linux-(2\.\d\.\d+(\.\d+)?(-rc\d+)?).tar')	
valid_kernel= re.compile('2\.\d\.\d+(\.\d+)?(-rc\d+)?(-(git|bk))\d+')

statuses = ['NOSTATUS', 'ERROR', 'ABORT', 'FAIL', 'WARN', 'GOOD']
status_num = {}
for x in range(0, len(statuses)):
	status_num[statuses[x]] = x


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
		self.machine = ''
		self.variables = {}
		self.tests = []
		self.kernel = None

		print 'FOOFACE ' + self.control
		if not os.path.exists(self.control):
			return
		# HACK. we don't have proper build tags in the status file yet
		# so we hardcode build/ and do it at the start of the job
		print 'POOFACE'
		self.kernel = kernel(os.path.join(dir, 'build'))
		self.grope_status()


	def derive_build(self, raw_build):
		# First to expand variables in the build line ...
		self.build = ''
		for element in re.split(r'(\$\w+)', raw_build):
			if element.startswith('$'):
				element = self.variables[element.lstrip('$')]
			self.build += element


	def derive_patches(self):
		self.patches_short = []
		self.patches_long = []
		for segment in re.split(r'(-p \S+)', self.build):
			if segment.startswith('-p'):
				self.patches_long.append(segment.split(' ')[1])
		self.patches_short = [shorten_patch(p) for p in self.patches_long]
		

	def grope_status(self):
		status_file = os.path.join(self.dir, "status")
		for line in open(status_file, 'r').readlines():
			(status, testname, reason) = line.rstrip().split(' ', 2)

		self.tests.append(test(testname, status, reason))


	def set_status(self, status):
		if status not in status_num:
			return
		self.status = status
		self.status_num = status_num[status]


class kernel:
	def __init__(self, builddir):
		self.base = None
		self.patches = []

		log = os.path.join(builddir, 'debug/build_log')
		patch_hashes = []
		for line in open(log, 'r'):
			(type, rest) = line.split(': ', 1)
			words = rest.split()
			if type == 'BUILD VERSION':
				self.base = words[0]
			if type == 'PATCH':
				self.patches.append(words[0:])
				# patch_hashes.append(words[2])
		self.kversion_hash = self.get_kversion_hash(self.base, patch_hashes)


	def get_kversion_hash(self, base, patch_hashes):
		"""\
		Calculate a hash representing the unique combination of
		the kernel base version plus 
		"""
		key_string = ','.join([base] + patch_hashes)
		return md5.new(key_string).hexdigest()


class test:
	def __init__(self, dir, status, reason):
		self.dir = dir
		self.status = status
		self.reason = reason
		self.keyval = os.path.join(dir, 'results/keyval')
		self.iterations = []
		self.testname = re.sub(r'\..*', '', self.dir)

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
