#!/usr/bin/python
print "Content-type: text/html\n"
import cgi, cgitb, os, sys, re
sys.stdout.flush()
cgitb.enable()

import common
from autotest_lib.tko import db, display, frontend

db = db.db()

benchmark_key = {
'kernbench' : 'elapsed',
'dbench' : 'throughput',
'tbench' : 'throughput',
}

def main():
    display.print_main_header()
    ## it is table only; mouse hovering off
    display.set_brief_mode() 

    rows = db.select('test', 'tests', {}, distinct = True)
    benchmarks = []
    for row in rows:
        benchmark = row[0]
        testname = re.sub(r'\..*', '', benchmark)
        if not benchmark_key.has_key(testname):
            continue
        benchmarks.append(benchmark)
    benchmarks = display.sort_tests(benchmarks)

    machine_idx = {}
    benchmark_data = {}
    for benchmark in benchmarks:
        fields = 'machine_idx,machine_hostname,count(status_word)'
        where = { 'subdir': benchmark, 'status_word' : 'GOOD' }
        data = {}
        for (idx, machine, count) in db.select(fields, 'test_view',
                    where, group_by = 'machine_hostname'):
            data[machine] = count
            machine_idx[machine] = idx
        benchmark_data[benchmark] = data

    print '<h1>Performance</h1>'

    header_row =  [ display.box('Benchmark', header=True) ]
    header_row += [ display.box(re.sub(r'\.', '<br>', benchmark), header=True) for benchmark in benchmarks ]

    matrix = [header_row]
    for machine in machine_idx:
        row = [display.box(machine)]
        for benchmark in benchmarks:
            count = benchmark_data[benchmark].get(machine, None)
            if not count:
                row.append(display.box(None))
                continue
            key = benchmark_key[re.sub(r'\..*', '', benchmark)]
            url = 'machine_test_attribute_graph.cgi'
            url += '?machine=' + str(machine_idx[machine])
            url += '&benchmark=' + benchmark
            url += '&key=' + key
            html = '<a href="%s">%d</a>' % (url, count)
            row.append(display.box(html))
        matrix.append(row)
    matrix.append(header_row)

    display.print_table(matrix)

main()
