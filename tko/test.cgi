#!/usr/bin/python
"""
Further display the tests in a matrix of the form tests X machines
to help understand the results selected from the previous form.
"""

print "Content-type: text/html\n"
import cgi, cgitb, os, sys, re
sys.stdout.flush()
cgitb.enable()

import common
from autotest_lib.tko import db, display, frontend

db = db.db()

def main():
    display.print_main_header()
    
    form = cgi.FieldStorage()

    if form.has_key('sql'):
        sql = form['sql'].value

    if form.has_key('values'):
        values = [val for val in form['values'].value.split(',')]

    if not sql:
        return
    if not values:
        return

    tests = frontend.test.select_sql(db, sql, values)

    # get the list of tests/machines to populate the row and column header.
    testname = [test.testname for test in tests]
    machine_idx = [test.machine_idx for test in tests]

    # We dont want repetitions in the table row/column headers,
    # so eliminate the dups.
    uniq_test = list(set(testname))
    uniq_machine_idx = list(set(machine_idx))

    header_row = [ display.box('', header = True) ]
    for test_name in uniq_test:
        header_row.append(display.box(test_name, header=True))
    matrix = [header_row]
    for machine in uniq_machine_idx:
        mach_name = db.select_sql('hostname', 'machines',
                 ' where machine_idx=%s', [str(machine)])
        row = [display.box(mach_name[0][0])]
        for test_name in uniq_test:
            testlist = [test for test in tests
                     if test.machine_idx == machine
                     and test.testname == test_name]
            # url link to the first test.
            # TODO: provide another level to show the different
            #    test results.
            link = None
            if testlist and testlist[0]:
                link = testlist[0].url
            box = display.status_count_box(db, testlist, link=link)
            row.append(box)
        matrix.append(row)
    display.print_table(matrix)

main()
