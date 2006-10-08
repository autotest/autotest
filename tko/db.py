import sqlite

class db:
	def __init__(self):
		self.con = sqlite.connect('tko_db')
		self.cur = self.con.cursor()


	def select(self, cmd):
		self.cur.execute('select ' + cmd)
		return self.cur.fetchall()

