import MySQLdb, re, os, sys, types

class db:
	def __init__(self, debug = False, autocommit=True):
		self.debug = debug
		self.autocommit = autocommit

		path = os.path.dirname(os.path.abspath(sys.argv[0]))
		try:
			file = os.path.join(path, '.database')
			db_prefs = open(file, 'r')
			host = db_prefs.readline().rstrip()
			database = db_prefs.readline().rstrip()
		except:
			host = 'localhost'
			database = 'tko'
	
		try:
			file = os.path.join(path, '.priv_login')
			login = open(file, 'r')
			user = login.readline().rstrip()
			password = login.readline().rstrip()
		except:	
			try:
				file = os.path.join(path, '.unpriv_login')
				login = open(file, 'r')
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
		status_rows = self.select('status_idx, word', 'status', None)
		for s in status_rows:
			self.status_idx[s[1]] = s[0]
			self.status_word[s[0]] = s[1]

		dir = os.path.abspath(os.path.dirname(sys.argv[0]))
		machine_map = os.path.join(dir, 'machines')
		if os.path.exists(machine_map):
			self.machine_map = machine_map
		self.machine_group = {}


	def dprint(self, value):
		if self.debug:
			sys.stderr.write('SQL: ' + str(value) + '\n')


	def commit(self):
		self.con.commit()


	def select(self, fields, table, where, distinct = False):
		"""\
			select fields from table where {dictionary}
		"""
		cmd = ['select']
		if distinct:
			cmd.append('distinct')
		cmd += [fields, 'from', table]

		values = []
		if where and isinstance(where, types.DictionaryType):
			keys = [field + '=%s' for field in where.keys()]
			values = [where[field] for field in where.keys()]

			cmd.append(' where ' + ' and '.join(keys))
		elif where and isinstance(where, types.StringTypes):
			cmd.append(' where ' + where)

		self.dprint('%s %s' % (' '.join(cmd),values))
		self.cur.execute(' '.join(cmd), values)
		return self.cur.fetchall()


	def select_sql(self, fields, table, sql, values):
		"""\
			select fields from table "sql"
		"""
		cmd = 'select %s from %s %s' % (fields, table, sql)
		self.dprint(cmd)
		self.cur.execute(cmd, values)
		return self.cur.fetchall()


	def insert(self, table, data, commit = None):
		"""\
			'insert into table (keys) values (%s ... %s)', values

			data:
				dictionary of fields and data
		"""
		if commit == None:
			commit = self.autocommit
		fields = data.keys()
		refs = ['%s' for field in fields]
		values = [data[field] for field in fields]
		cmd = 'insert into %s (%s) values (%s)' % \
				(table, ','.join(fields), ','.join(refs))

		self.dprint('%s %s' % (cmd,values))
		self.cur.execute(cmd, values)
		if commit:
			self.con.commit()


	def update(self, table, data, where, commit = None):
		"""\
			'update table set data values (%s ... %s) where ...'

			data:
				dictionary of fields and data
		"""
		if commit == None:
			commit = self.autocommit
		cmd = 'update %s ' % table
		fields = data.keys()
		data_refs = [field + '=%s' for field in fields]
		data_values = [data[field] for field in fields]
		cmd += ' set ' + ' and '.join(data_refs)

		where_keys = [field + '=%s' for field in where.keys()]
		where_values = [where[field] for field in where.keys()]
		cmd += ' where ' + ' and '.join(where_keys)

		print '%s %s' % (cmd, data_values + where_values)
		self.cur.execute(cmd, data_values + where_values)
		if commit:
			self.con.commit()


	def insert_job(self, tag, job, commit = None):
		job.machine_idx = self.lookup_machine(job.machine)
		if not job.machine_idx:
			job.machine_idx = self.insert_machine(job.machine,
		                                              commit=commit)
		self.insert('jobs',
		            {'tag':tag,
		             'machine_idx':job.machine_idx},
                            commit=commit)
		job.index = self.find_job(tag)
		for test in job.tests:
			self.insert_test(job, test, commit=commit)

	def insert_test(self, job, test, commit = None):
		kver = self.insert_kernel(test.kernel, commit=commit)
		data = {'job_idx':job.index, 'test':test.testname,
			'subdir':test.subdir, 'kernel_idx':kver,
			'status':self.status_idx[test.status],
			'reason':test.reason, 'machine_idx':job.machine_idx }
		self.insert('tests', data, commit=commit)
		test_idx = self.find_test(job.index, test.subdir)
		data = { 'test_idx':test_idx }

		for i in test.iterations:
			data['iteration'] = i.index
			for key in i.keyval:
				data['attribute'] = key
				data['value'] = i.keyval[key]
				self.insert('iteration_result',
                                            data,
                                            commit=commit)


	def read_machine_map(self):
		self.machine_group = {}
		for line in open(self.machine_map, 'r').readlines():
			(machine, group) = line.split()
			self.machine_group[machine] = group


	def insert_machine(self, hostname, group = None, commit = None):
		if self.machine_map and not self.machine_group:
			self.read_machine_map()

		if not group:
			group = self.machine_group.get(hostname, hostname)
				
		self.insert('machines',
                            { 'hostname' : hostname ,
		              'machine_group' : group },
		            commit=commit)
		return self.lookup_machine(hostname)


	def lookup_machine(self, hostname):
		where = { 'hostname' : hostname }
		rows = self.select('machine_idx', 'machines', where)
		if rows:
			return rows[0][0]
		else:
			return None


	def lookup_kernel(self, kernel):
		rows = self.select('kernel_idx', 'kernels', 
					{'kernel_hash':kernel.kernel_hash})
		if rows:
			return rows[0][0]
		else:
			return None


	def insert_kernel(self, kernel, commit = None):
		kver = self.lookup_kernel(kernel)
		if kver:
			return kver
		self.insert('kernels',
                            {'base':kernel.base,
		             'kernel_hash':kernel.kernel_hash,
		             'printable':kernel.base},
		            commit=commit)
		# WARNING - incorrectly shoving base into printable here.
		kver = self.lookup_kernel(kernel)
		for patch in kernel.patches:
			self.insert_patch(kver, patch, commit=commit)
		return kver


	def insert_patch(self, kver, patch, commit = None):
		print patch.reference
		name = os.path.basename(patch.reference)[:80]
		self.insert('patches',
                            {'kernel_idx': kver, 
		             'name':name,
		             'url':patch.reference, 
		             'hash':patch.hash},
                            commit=commit)


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
