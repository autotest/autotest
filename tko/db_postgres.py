import psycopg2.psycopg1 as postgres
import db

class db_postgres(db.db_sql):
	def connect(self, host, database, user, password):
		return postgres.connect("dbname=%s user=%s password=%s" % \
				(database, user, password))
