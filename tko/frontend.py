#!/usr/bin/python
import os, re, db

# Pulling hierarchy:
#
# test pulls in (kernel, job, attributes, iterations)
# kernel pulls in (patches)
#
# Note that job does put pull test - test is the primary object.

html_root = 'http://test.kernel.org/google/'

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
	def select(klass, db, where = {}, distinct = False):
		fields = ['test_idx', 'job_idx', 'test', 'subdir', 
			  'kernel_idx', 'status', 'reason', 'machine']
		tests = []
		for row in db.select(','.join(fields), 'tests', where, distinct):
			tests.append(klass(db, *row))
		return tests


	def __init__(self, db, test_idx, job_idx, testname, subdir, kernel_idx, status_num, reason, machine):
		self.idx = test_idx
		self.job = job(db, job_idx)
		# self.machine = self.job.machine
		self.testname = testname
		self.subdir = subdir
		self.kernel_idx = kernel_idx
		self.__kernel = None
		self.__iterations = None
		self.status_num = status_num
		self.status_word = db.status_word[status_num]
		self.reason = reason
		self.db = db
		if self.subdir:
			self.url = html_root + self.job.tag + '/' + self.subdir
		else:
			self.url = None



	def iterations(self):
		"""
		Caching function for iterations
		"""
		if not self.__iterations:
			self.__iterations = {}
			# A dictionary - dict{key} = [value1, value2, ....]
			where = {'test_idx' : self.idx}
			for i in iteration.select(self.db, where):
				if self.__iterations.has_key(i.key):
					self.__iterations[i.key].append(i.value)
				else:
					self.__iterations[i.key] = [i.value]
		return self.__iterations
			

	def kernel(self):
		"""
		Caching function for kernels
		"""
		if not self.__kernel:
			where = {'kernel_idx' : self.kernel_idx}
			self.__kernel = kernel.select(self.db, where)[0]
		return self.__kernel


class job:
	def __init__(self, db, job_idx):
		where = {'job_idx' : job_idx}
		rows = db.select('tag, machine', 'jobs', where)
		if not rows:
			return None
		(self.tag, self.machine) = rows[0]

 
class iteration:
	@classmethod
	def select(klass, db, where):
		fields = ['iteration', 'attribute', 'value']
		iterations = []
		rows = db.select(','.join(fields), 'iteration_result', where)
		for row in rows:
			iterations.append(klass(*row))
		return iterations


	def __init__(self, iteration, key, value):
 		self.iteration = iteration
		self.key = key
		self.value = value

# class patch:
# 	def __init__(self):
# 		self.spec = None
