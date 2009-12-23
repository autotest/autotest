#!/usr/bin/python

import common
import MySQLdb
import sys
from autotest_lib.client.common_lib import global_config

if (len(sys.argv) < 2 or
    [arg for arg in sys.argv[1:] if arg.startswith('-')]):
    print "Usage: %s username [username ...]" %sys.argv[0]
    sys.exit(1)

config = global_config.global_config
section = 'AUTOTEST_WEB'
host = config.get_config_value(section, "host")
db_name = config.get_config_value(section, "database")
user = config.get_config_value(section, "user")
password = config.get_config_value(section, "password")

con = MySQLdb.connect(host=host, user=user,
                      passwd=password, db=db_name)
cur = con.cursor()

for username in sys.argv[1:]:
    cur.execute("""
        SELECT access_level
        FROM afe_users
        WHERE login = %s""", username)
    row = cur.fetchone()

    if row is None:
        print "User %s does not exist. Creating..." % username
        cur.execute("""
            INSERT INTO afe_users (login, access_level)
            VALUES (%s, 100)""", username)
        print "    Done"
    else:
        print "Updating user %s..." % username
        cur.execute("""
            UPDATE afe_users
            SET access_level = 100
            WHERE login = %s""", username)
        if (cur.rowcount == 1):
            print "    Done"
        else:
            print "    %s is already a superuser!" % username

cur.close()
con.commit()
con.close()
