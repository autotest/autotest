import sqlite, re

class db:
	def __init__(self):
		self.con = sqlite.connect('tko_db')
		self.cur = self.con.cursor()


	def select(self, fields, table, where_dict):
		"""\
			select fields from table where {dictionary}
		"""
		keys = [field + '=%s' for field in where_dict.keys()]
		values = [where_dict[field] for field in where_dict.keys()]

		where = 'and'.join(keys)
		cmd = 'select %s from %s where %s' % (fields, table, where)
		print cmd
		print values
		self.cur.execute(cmd, values)
		return self.cur.fetchall()


	def insert(self, table, data):
		"""\
			'insert into table (keys) values (%s ... %s)', values

			data:
				dictionary of fields and data
		"""
		fields = data.keys()
		refs = ['%s' for field in fields]
		values = [data[field] for field in fields]
		cmd = 'insert into %s (%s) values (%s)' % \
				(table, ','.join(fields), ','.join(refs))
		print cmd
		print values
		self.cur.execute(cmd, values)
		self.con.commit()


	def insert_job(self, tag, job):
		# is kernel version in tree?
		self.insert('jobs', {'tag':tag, 'machine':'UNKNOWN'})
		job.index = self.find_job(tag)
		for test in job.tests:
			self.insert_test(job, test)

	def insert_test(self, job, test):
		# WE ARE MISSING KVERSION HERE!!!!
		data = {'job_idx':job.index, 'test':test.testname,
			'subdir':test.dir, 
			'status':test.status, 'reason':test.reason}
		self.insert('tests', data)


	def lookup_kernel_version(self, base, patches):
		return self.select('kversion', 'kversions', {'base':base})[0]


	def insert_kernel_version(self, base, patches):
		self.insert('kversions', {'base': base})


	def find_job(self, tag):
		rows = self.select('job_idx', 'jobs', {'tag': tag})
		if rows:
			return rows[0][0]
		else:
			return None
