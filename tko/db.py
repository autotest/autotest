import sqlite, re, os

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
		self.insert('jobs', {'tag':tag, 'machine':'UNKNOWN'})
		job.index = self.find_job(tag)
		for test in job.tests:
			self.insert_test(job, test)


	def insert_test(self, job, test):
		kver = self.insert_kernel_version(test.kernel)
		data = {'job_idx':job.index, 'test':test.testname,
			'subdir':test.dir, 
			'status':test.status, 'reason':test.reason}
		self.insert('tests', data)


	def lookup_kversion(self, kernel):
		rows = self.select('kversion', 'kversions', 
				{'kversion_hash':kernel.kversion_hash})
		if rows:
			return rows[0][0]
		else:
			return None


	def insert_kernel_version(self, kernel):
		kver = self.lookup_kversion(kernel)
		if kver:
			return kver
		self.insert('kversions', {'base':kernel.base,
					  'kversion_hash':kernel.kversion_hash})
		kver = self.lookup_kversion(kernel)
		for patch in kernel.patches:
			self.insert_patch(kver, patch)
		return kver


	def insert_patch(self, kver, patch):
		print patch.reference
		name = os.path.basename(patch.reference)[:80]
		self.insert('patches', {'kversion': kver, 
					'name':name,
					'url':patch.reference, 
					'hash':patch.hash})


	def find_job(self, tag):
		rows = self.select('job_idx', 'jobs', {'tag': tag})
		if rows:
			return rows[0][0]
		else:
			return None
