#!/usr/bin/python2.4
import os, re

valid_users = r'(apw|mbligh|andyw|korgtest)'
build_stock = re.compile('build generic stock (2\.\S+)')	
build_url   = re.compile('build generic url (\S+)(?:\s+-p\s+(\S+))?')	
valid_patch = re.compile('patch-(2\.\d\.\d+(\.\d+)?(-rc\d+)?(-(git|bk))\d+)?)')
valid_kernel= re.compile('linux-(2\.\d\.\d+(\.\d+)?(-rc\d+)?).tar')

class job:
	def __init__(self, topdir, key):
		self.topdir = topdir
		self.control = "%s/autobench.dat" % topdir
		self.variables = {}
		self.kernel = None

		if os.path.exists(self.control):
			self.grope_datfile()


	def grope_datfile(self):
		variables = self.variables
		for line in open(self.control, 'r').readlines():
			if line.startswith('+$'):
				match = re.match(r'\+\$(\S+)\s+(\S?.*)', line)
				variables[match.group(1)] = match.group(2)
			if line.startswith('build '):
				self.derive_build(line)

		if not re.match(valid_users, variables['username']):
			raise "bad username - %s" % variables['username']

		self.derive_patches()
		self.derive_kernel()


	def derive_build(self, raw_build):
		# First to expand variables in the build line ...
		self.build = ''
		for element in re.split(r'(\$\w+)', raw_build):
			if element.startswith('$'):
				element = variables[element.lstrip('$')]
			self.build += element


	# This is FOUL. we ought to be recording the data in kernel.build()
	def derive_kernel(self):
		# look for 'build generic stock' .... this is easy
		match = build_stock.match(self.build)
		if match:
			self.kernel = match.group(1)

		# look for 'build generic url' .... this is harder, as we
		# have to cope with patches that may set the kernel version
		m = build_url.match(self.build)
		if m:
			kernel = m.group(1).basename()
			k = valid_kernel.match(kernel)
			if k:
				self.kernel = k.group(1)
			if m.group(2):			# there's a -p option
				patch = m.group(2).basename()
				p = valid_patch.match(patch)
				if p:
					self.kernel = p.group(1)
		
