#!/usr/bin/python
import os, re, db, sys

tko = os.path.dirname(os.path.realpath(os.path.abspath(sys.argv[0])))
root_url_file = os.path.join(tko, '.root_url')
if os.path.exists(root_url_file):
        html_root = open(root_url_file, 'r').readline().rstrip()
else:
        html_root = '/results/'

def select(db, field, value=None, distinct=False):
	""" returns the relevant index values where the field value matches the
	    input value to the function.
	    If there is no value passed, then it returns the index values and the
	    field values corresponsing to them. """

	fields = { 'kernel': ['printable', 'kernel_idx', 'kernel_idx'],
	 	   'machine_group': ['machine_group', 'machine_idx', 'machine_idx'],
		   'hostname': ['hostname', 'machine_idx', 'machine_idx'],
		   'label': ['label', 'job_idx', 'job_idx'],
		   'tag': ['tag', 'job_idx', 'job_idx'],
	           'job': ['job_idx', 'job_idx', 'job_idx'],
		   'user': ['username', 'job_idx', 'job_idx'],
		   'test': ['test', 'test', 'test'],
		   'status': ['word', 'status_idx', 'status'],
		   'reason': ['reason', 'test_idx', 'test_idx'] }
	table = { 'kernel': 'kernels',
		  'machine_group': 'machines',
		  'hostname': 'machines',
		  'label': 'jobs',
		  'tag': 'jobs',
	          'job': 'jobs',
		  'user': 'jobs',
		  'test': 'tests',
		  'status': 'status',
		  'reason': 'tests' }

	lookup_field, idx_field, field_name_in_main_table = fields[field]
	tablename = table[field]
	# select all the index values that match the given field name.
	sql = ""
	if distinct:
		sql += " distinct "
	if not value:
		sql += " %s , %s " % (lookup_field, idx_field)
		where = " %s is not null " % lookup_field
	else:
		sql += "%s " % idx_field
		if field == 'tag':
			where = " %s LIKE %s " % (lookup_field, value)
		else:
			where = " %s = %s " % (lookup_field, value)

	match = db.select(sql, tablename, where)
	# returns the value and its field name
	return match, field_name_in_main_table


def get_axis_data(axis):
	rows = db.select(axis , 'test_view', distinct = True)
	# Need to do a magic sort here if axis == 'kernel_printable'
	return sorted([row[0] for row in rows])


def get_matrix_data(db, x_axis, y_axis, where = None):
	# Return a 3-d hash of data - [x-value][y-value][status_word]
	# Searches on the test_view table - x_axis and y_axis must both be
	# column names in that table.
	assert x_axis != y_axis
	fields = '%s, %s, status, COUNT(status_word)' % (x_axis, y_axis)
	group_by = '%s, %s, status' % (x_axis, y_axis)
	rows = db.select(fields, 'test_view', where=where, group_by=group_by)

	data = {}
	for (x, y, status, count) in rows:
		if not data.has_key(x):
			data[x] = {}
		if not data[x].has_key(y):
			data[x][y] = {}
		data[x][y][status] = count
	return data


class anygroup:
	@classmethod
	def selectunique(klass, db, field):
		"""Return unique values for all possible groups within
		 the table."""
		rows, field_name_in_main_table = select(db, field, value=None, distinct=True)
		groupnames = sorted([row for row in rows])

		# collapse duplicates where records have the same name but
		# multiple index values
		headers = {}
		for field_name, idx_value in groupnames:
			if headers.has_key(field_name):
				headers[field_name].append(idx_value)
			else:
				headers[field_name] = [idx_value]
		headers = headers.items()
		headers.sort()
		return [klass(db, field_name_in_main_table, groupname) for groupname in headers]


	def __init__(self, db, idx_name, name):
		self.db = db
		self.name = name[0]
		self.idx_name = idx_name
		self.idx_value = name[1]


class group:
	@classmethod
	def select(klass, db):
		"""Return all possible machine groups"""
		rows = db.select('distinct machine_group', 'machines',
						'machine_group is not null')
		groupnames = sorted([row[0] for row in rows])
		return [klass(db, groupname) for groupname in groupnames]


	def __init__(self, db, name):
		self.name = name
		self.db = db


	def machines(self):
		return machine.select(self.db, { 'machine_group' : self.name })


	def tests(self, where = {}):
		values = [self.name]
		sql = 't inner join machines m on m.machine_idx=t.machine_idx where m.machine_group=%s'
		for key in where.keys():
			sql += ' and %s=%%s' % key
			values.append(where[key])
		return test.select_sql(self.db, sql, values)


class machine:
	@classmethod
	def select(klass, db, where = {}):
		fields = ['machine_idx', 'hostname', 'machine_group', 'owner']
		machines = []
		for row in db.select(','.join(fields), 'machines', where):
			machines.append(klass(db, *row))
		return machines


	def __init__(self, db, idx, hostname, group, owner):
		self.db = db
		self.idx = idx
		self.hostname = hostname
		self.group = group
		if owner:
			if len(owner) > 3:
				self.owner = owner.capitalize()
			else:
				# capitalize acroymns
				self.owner = owner.upper()
		else:
			self.owner = None


class kernel:
	@classmethod
	def select(klass, db, where = {}):
		fields = ['kernel_idx', 'kernel_hash', 'base', 'printable']
		rows = db.select(','.join(fields), 'kernels', where)
		return [klass(db, *row) for row in rows]


	def __init__(self, db, idx, hash, base, printable):
		self.db = db
		self.idx = idx
		self.hash = hash
		self.base = base
		self.printable = printable
		self.patches = []    # THIS SHOULD PULL IN PATCHES!


class test:
	@classmethod
	def select(klass, db, where = {}, wherein = {}, distinct = False):
		fields = ['test_idx', 'job_idx', 'test', 'subdir', 
			  'kernel_idx', 'status', 'reason', 'machine_idx']
		tests = []
		for row in db.select(','.join(fields), 'tests', where, wherein,distinct):
			tests.append(klass(db, *row))
		return tests


	@classmethod
	def select_sql(klass, db, sql, values):
		fields = ['test_idx', 'job_idx', 'test', 'subdir', 
			  'kernel_idx', 'status', 'reason', 'machine_idx']
		fields = ['t.'+field for field in fields]
		rows = db.select_sql(','.join(fields), 'tests', sql, values)
		return [klass(db, *row) for row in rows]

		
	def __init__(self, db, test_idx, job_idx, testname, subdir, kernel_idx, status_num, reason, machine_idx):
		self.idx = test_idx
		self.job = job(db, job_idx)
		self.testname = testname
		self.subdir = subdir
		self.kernel_idx = kernel_idx
		self.__kernel = None
		self.__iterations = None
		self.machine_idx = machine_idx
		self.__machine = None
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


	def machine(self):
		"""
		Caching function for kernels
		"""
		if not self.__machine:
			where = {'machine_idx' : self.machine_idx}
			self.__machine = machine.select(self.db, where)[0]
		return self.__machine


class job:
	def __init__(self, db, job_idx):
		where = {'job_idx' : job_idx}
		rows = db.select('tag, machine_idx', 'jobs', where)
		if not rows:
			return None
		(self.tag, self.machine_idx) = rows[0]
		self.job_idx = job_idx

 
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
