import common
import MySQLdb as driver
import db

class db_mysql(db.db_sql):
    def connect(self, host, database, user, password):
        return driver.connect(host=host, user=user,
                              passwd=password, db=database)
