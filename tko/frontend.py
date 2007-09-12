#!/usr/bin/python
import os, re, db

statuses = ['NOSTATUS', 'ERROR', 'ABORT', 'FAIL', 'WARN', 'GOOD']
status_num = {}
for x in range(0, len(statuses)):
	status_num[statuses[x]] = x


class job:
	def __init__(self):
		self.idx = None
		self.tag = None
		self.machine = None
		self.tests = []


class kernel:
	fields = ['kernel_idx', 'kernel_hash', 'base', 'printable']

	def __init__(self, db, where):
		self.db = db
		self.base = None
		self.patches = []

		db.select(fields, kernels, 

		
class patch:
	def __init__(self):
		self.spec = spec
		self.reference = reference
		self.hash = hash


class test:
	def __init__(self, dir, status, reason, kernel):
		self.dir = dir
		self.status = status
		self.reason = reason
		self.keyval = os.path.join(dir, 'results/keyval')
		self.iterations = []
		self.testname = re.sub(r'\..*', '', self.dir)
		self.kernel = kernel


class iteration:
	def __init__(self, index, lines):
		self.index = index
		self.keyval = {}

