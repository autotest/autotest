import psycopg2.psycopg1 as driver
import db

class db_postgres(db.db_sql):
    def connect(self, host, database, user, password):
        return driver.connect("dbname=%s user=%s password=%s" % \
                              (database, user, password))
