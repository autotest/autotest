import MySQLdb, re, os, sys

class db:
	def __init__(self, debug = False):
		self.debug = debug
			
		try:
			db_prefs = open('.database', 'r')
			host = db_prefs.readline().rstrip()
			database = db_prefs.readline().rstrip()
		except:
			host = 'localhost'
			database = 'tko'
	
		try:
			login = open('.priv_login', 'r')
			user = login.readline().rstrip()
			password = login.readline().rstrip()
	        except:	
		        try:
			        login = open('.unpriv_login', 'r')
			        user = login.readline().rstrip()
			        password = login.readline().rstrip()
		        except:
			        user = 'nobody'
			        password = ''

		self.con = MySQLdb.connect(host=host, user=user,
                                           passwd=password, db=database)
		self.cur = self.con.cursor()

		# if not present, insert statuses
		self.status_idx = {}
		self.status_word = {}
		for s in ['NOSTATUS', 'ERROR', 'ABORT', 'FAIL', 'WARN', 'GOOD']:
			idx = self.get_status(s)
			if not idx:
				self.insert('status', {'word' : s})
				idx = self.get_status(s)
			self.status_idx[s] = idx
			self.status_word[idx] = s
		

	def get_status(self, word):
		rows = self.select('status_idx', 'status', {'word' : word})
		if rows:
			return rows[0][0]
		else:
			return None


	def dprint(self, value):
		if self.debug:
			sys.stderr.write('SQL: ' + str(value) + '\n')


	def select(self, fields, table, where, distinct = False):
		"""\
			select fields from table where {dictionary}
		"""
		cmd = ['select']
		if distinct:
			cmd.append('distinct')
		cmd += [fields, 'from', table]

		values = []
		if where:
			keys = [field + '=%s' for field in where.keys()]
			values = [where[field] for field in where.keys()]

			cmd.append(' where ' + ' and '.join(keys))

		self.dprint('%s %s' % (' '.join(cmd),values))
		self.cur.execute(' '.join(cmd), values)
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

		self.dprint('%s %s' % (cmd,values))
		self.cur.execute(cmd, values)
		self.con.commit()


	def insert_job(self, tag, job):
		self.insert('jobs', {'tag':tag, 'machine':job.machine})
		job.index = self.find_job(tag)
		for test in job.tests:
			self.insert_test(job, test)


	def insert_test(self, job, test):
		kver = self.insert_kernel(test.kernel)
		data = {'job_idx':job.index, 'test':test.testname,
			'subdir':test.subdir, 'kernel_idx':kver,
			'status':self.status_idx[test.status],
			'reason':test.reason, 'machine':test.machine }
		self.insert('tests', data)
		test_idx = self.find_test(job.index, test.subdir)
		data = { 'test_idx':test_idx }

		for i in test.iterations:
			data['iteration'] = i.index
			for key in i.keyval:
				data['attribute'] = key
				data['value'] = i.keyval[key]
				self.insert('iteration_result', data)


	def lookup_kernel(self, kernel):
		rows = self.select('kernel_idx', 'kernels', 
				{'kernel_hash':kernel.kernel_hash})
		if rows:
			return rows[0][0]
		else:
			return None


	def insert_kernel(self, kernel):
		kver = self.lookup_kernel(kernel)
		if kver:
			return kver
		self.insert('kernels', {'base':kernel.base,
					  'kernel_hash':kernel.kernel_hash,
					  'printable':kernel.base})
		# WARNING - incorrectly shoving base into printable here.
		kver = self.lookup_kernel(kernel)
		for patch in kernel.patches:
			self.insert_patch(kver, patch)
		return kver


	def insert_patch(self, kver, patch):
		print patch.reference
		name = os.path.basename(patch.reference)[:80]
		self.insert('patches', {'kernel_idx': kver, 
					'name':name,
					'url':patch.reference, 
					'hash':patch.hash})

	def find_test(self, job_idx, subdir):
		where = { 'job_idx':job_idx , 'subdir':subdir }
		rows = self.select('test_idx', 'tests', where)
		if rows:
			return rows[0][0]
		else:
			return None


	def find_job(self, tag):
		rows = self.select('job_idx', 'jobs', {'tag': tag})
		if rows:
			return rows[0][0]
		else:
			return None
