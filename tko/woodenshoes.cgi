#!/usr/bin/python

"""
Selects all rows and columns that satisfy the condition specified
and draws the matrix. There is a seperate SQL query made for every (x,y)
in the matrix.
"""
print "Content-type: text/html\n"  # application/json ?
import cgi, cgitb
import re, sys, os

import common
from autotest_lib.tko import frontend, db, query_lib

cgitb.enable()
db_obj = db.db()
form = cgi.FieldStorage()

COLUMN_NAMES = ['time', 'tag', 'status', 'test', 'start_time']
columns = [frontend.test_view_field_dict[x] for x in COLUMN_NAMES]

condition = query_lib.parse_scrub_and_gen_condition(form['condition'].value,
        frontend.test_view_field_dict)


def main():
    fmt = '{"date":"%s", "job-id":"%s", "result":"%s", ' + \
            '"test_name":"%s", "log_url":"%s", "start_date":"%s"}'
    output = []
    for row in db_obj.select(','.join(columns), 'test_view', condition):
        line = fmt % (row[0], row[1], row[2], row[3],
                      'http://autotest/results/' + row[1], row[4])
        output.append(line)
    print '[%s]' % (",\n".join(output))


main()
