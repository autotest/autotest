import sqlite, re

class db:
	def __init__(self):
		self.con = sqlite.connect('tko_db')
		self.cur = self.con.cursor()


	def select(self, cmd):
		print 'select ' + cmd
		self.cur.execute('select ' + cmd)
		return self.cur.fetchall()


	def insert_job(self, tag, job):
		# is kernel version in tree?
		command = 'insert into jobs ' + \
			'(tag, machine) ' + \
			'values (%s, %s) '
		print command
		values = (tag, 'UNKNOWN')
		self.cur.execute(command, values)
		self.con.commit()
		# Select it back from the job table and find the uniq key


	def insert_test(self, job, 
	def lookup_kernel_version(base, patches):
		command = 'select kversion from kversions where base = %s'


	def insert_kernel_version(base, patches):
		base = re.sub(r'\+.*', '', printable)
		command = 'select kversion from kversions where printable = %s'
		self.cur.execute(command, tag)
		results = self.cur.fetchall()
		if results:
			return results[0]
		command = 'insert into kversions (printable, base) ' + \
			  'values (%s, %s)'
		self.cur.execute(command, (printable, base))
		self.con.commit()


	def find_job(self, tag):
		command = 'select * from jobs where tag = %s'
		self.cur.execute(command, tag)
		return self.cur.fetchall()
