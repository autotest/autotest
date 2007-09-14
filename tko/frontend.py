#!/usr/bin/python
import os, re, db

# Pulling hierarchy:
#
# test pulls in (kernel, job, attributes, iterations)
# kernel pulls in (patches)
#
# Note that job does put pull test - test is the primary object.

status_colour = {
	'GOOD'          : '#66ff66', # green
	'WARN'          : '#fffc00', # yellow
	'FAIL'          : '#fff666', # red
	'ABORT'         : '#ff6666', # red
	'ERROR'         : '#ff6666', # red
	'NOSTATUS'      : '#ffffff', # white
	''		: '#ffffff', # white
}

class kernel:
	@classmethod
	def select(klass, db, where = {}):
		fields = ['kernel_idx', 'kernel_hash', 'base', 'printable']
		kernels = []
		for row in db.select(','.join(fields), 'kernels', where):
			kernels.append(klass(db, *row))
		return kernels


	def __init__(self, db, idx, hash, base, printable):
		self.db = db
		self.idx = idx
		self.hash = hash
		self.base = base
		self.printable = printable
		self.patches = []    # THIS SHOULD PULL IN PATCHES!


class test:
	@classmethod
	def select(klass, db, where = {}):
		fields = ['test_idx', 'job_idx', 'test', 'subdir', 
			  'kernel_idx', 'status', 'reason', 'machine']
		tests = []
		for row in db.select(','.join(fields), 'tests', where):
			tests.append(klass(db, *row))
		return tests


	def __init__(self, db, test_idx, job_idx, testname, subdir, kernel_idx, status_num, reason, machine):
		self.idx = test_idx
		self.job = None 
		# self.job = job.select(db, {'job_idx' : job_idx})
		# self.machine = self.job.machine
		self.test = testname
		self.subdir = subdir
		self.kernel = None
		# self.kernel = kernel.select(db, {'kernel_idx' : kernel_idx})
		self.status_num = status_num
		self.status_word = db.status_word[status_num]
		self.reason = reason
		
 
 
# class patch:
# 	def __init__(self):
# 		self.spec = None
# 
# 
# class iteration:
# 	def __init__(self):
# 		self.a = None
# 
