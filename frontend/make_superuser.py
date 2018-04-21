#!/usr/bin/python

try:
    import autotest.common as common  # pylint: disable=W0611
except ImportError:
    import common  # pylint: disable=W0611
import sys

import MySQLdb
from autotest.client.shared.settings import settings

if (len(sys.argv) < 2 or
        [arg for arg in sys.argv[1:] if arg.startswith('-')]):
    print("Usage: %s username [username ...]" % sys.argv[0])
    sys.exit(1)

section = 'AUTOTEST_WEB'
host = settings.get_value(section, "host")
db_name = settings.get_value(section, "database")
user = settings.get_value(section, "user")
password = settings.get_value(section, "password")

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
        print("User %s does not exist. Creating..." % username)
        cur.execute("""
            INSERT INTO afe_users (login, access_level)
            VALUES (%s, 100)""", username)
        print("    Done")
    else:
        print("Updating user %s..." % username)
        cur.execute("""
            UPDATE afe_users
            SET access_level = 100
            WHERE login = %s""", username)
        if (cur.rowcount == 1):
            print("    Done")
        else:
            print("    %s is already a superuser!" % username)

cur.close()
con.commit()
con.close()
