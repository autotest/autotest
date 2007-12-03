import MySQLdb
import db

class db_mysql(db.db_sql):
	def connect(self, host, database, user, password):
		return MySQLdb.connect(host=host, user=user,
			passwd=password, db=database)
