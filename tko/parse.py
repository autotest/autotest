#!/usr/bin/python2.4
import os, re

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


class parse:
	def __init__(self, topdir):
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
				element = self.variables[element.lstrip('$')]
			self.build += element


	def derive_patches(self):
		self.patches_short = []
		self.patches_long = []
		for segment in re.split(r'(-p \S+)', self.build):
			if segment.startswith('-p'):
				self.patches_long.append(segment.split(' ')[1])
		self.patches_short = [shorten_patch(p) for p in self.patches_long]
		
		
	# This is FOUL. we ought to be recording the data in kernel.build()
	def derive_kernel(self):
		# look for 'build generic stock' .... this is easy
		match = build_stock.match(self.build)
		if match:
			self.kernel = match.group(1)

		# look for 'build generic url' .... this is harder, as we
		# have to cope with patches that may set the kernel version
		match = build_url.match(self.build)
		if match:
			self.kernel = match.group(1)

		if not self.patches_short:
			return
		match = valid_kernel.match(self.patches_short[0])
		if match:
			self.kernel = match.group()
		
