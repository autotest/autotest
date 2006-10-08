import sqlite

class db:
	def __init__(self):
		self.con = sqlite.connect('tko_db')
		self.cur = self.con.cursor()


	def select(self, cmd):
		print 'select ' + cmd
		self.cur.execute('select ' + cmd)
		return self.cur.fetchall()


	def insert_job(self, tag, job):
		command = 'insert into jobs ' + \
			'(job, version, status, reason, machine, kernel) ' +\
			'values (%s, %s, %s, %s, %s, %s) '
		values = (tag, job.kernel, job.status_num, job.reason, \
			 job.machine, job.kernel)
		self.cur.execute(command, values)
		self.con.commit();


	def find_job(self, tag):
		command = 'select * from jobs where job = %s'
		self.cur.execute(command, tag)
		return self.cur.fetchall()
