#!/usr/bin/python
print "Content-type: text/html\n"
import cgi, cgitb, os, sys, re
sys.stdout.flush()
cgitb.enable()

import common
from autotest_lib.tko import db, display, frontend

db = db.db()

benchmark_key = {
'kernbench' : ["elapsed"],
'dbench' : ["throughput"],
'tbench' : ["throughput"],
}

def main():
    display.print_main_header()
    ## it is table only; mouse hovering off
    display.set_brief_mode()

    ## getting available tests
    rows = db.select('test', 'tests', {}, distinct=True)
    all_benchmarks = []
    for row in rows:
        benchmark = row[0]
        testname = re.sub(r'\..*', '', benchmark)
        all_benchmarks.append(benchmark)
    all_benchmarks = display.sort_tests(all_benchmarks)

    available_params = set()
    for benchmark in all_benchmarks:
        fields_tests = 'test_idx, count(status_word)'
        where_tests = { 'subdir': benchmark, 'status_word' : 'GOOD' }
        fields_params = 'attribute'
        for (id, count) in db.select(fields_tests, 'test_view',
                                     where_tests, group_by='machine_hostname'):
            where_params = {'test_idx': id}
            for (attribute) in db.select(fields_params, 'iteration_result',
                                         where_params):
                available_params.add("%s - %s" % (benchmark,
                                                     attribute[0]))
    available_params = list(available_params)
    #process form submit
    cleared = ""
    attributes = ""
    params = []
    attr = cgi.FieldStorage()
    if attr.has_key("cleared"):
        cleared = attr["cleared"].value
    if attr.has_key("reset"):
        cleared = ""
    if attr.has_key("clear") or cleared == "true":
        benchmark_key.clear()
        cleared = "true"
    else:
        attributes = "|".join(["%s:%s" % (key, value[0]) for key, value in benchmark_key.items()])

    if attr.has_key("add"):
        val = attr["key"].value.split("-")
        test = val[0].strip()
        key = val[1].strip()
        attributes = attr.getvalue("attributes", "")
        tk = "%s:%s" % (test, key)
        if len(attributes) == 0:
            attributes = tk
        elif attributes.find(tk) == -1:
            attributes += "|%s" % (tk)

        params = attributes.split("|")

    print '<h1>Add tests</h1>'
    display.print_add_test_form(available_params, attributes, cleared)

    #convert params to a dictionary
    for param in params:
        test_attributes = param.split(":")
        if not benchmark_key.has_key(test_attributes[0]):
            benchmark_key[test_attributes[0]] = []
        if benchmark_key[test_attributes[0]].count(test_attributes[1]) == 0:
            benchmark_key[test_attributes[0]].append(test_attributes[1])

    machine_idx = {}
    benchmark_data = {}
    for benchmark in benchmark_key:
        fields = 'machine_idx,machine_hostname,count(status_word)'
        where = { 'subdir': benchmark, 'status_word' : 'GOOD' }
        data = {}
        for (idx, machine, count) in db.select(fields, 'test_view',
                                            where, group_by='machine_hostname'):
            data[machine] = count
            machine_idx[machine] = idx
        benchmark_data[benchmark] = data


    print '<h1>Performance</h1>'

    header_row = [ display.box('Benchmark', header=True) ]
    for benchmark in benchmark_key:
        header_row += [ display.box("%s - %s" % (re.sub(r'\.', '<br>', benchmark),key), header=True) for key in benchmark_key[benchmark] ]
 
    matrix = [header_row]
    for machine in machine_idx:
        row = [display.box(machine)]
        for benchmark in benchmark_key:
            count = benchmark_data[benchmark].get(machine, None)
            if not count:
                row.append(display.box(None))
                continue
            for key in benchmark_key[re.sub(r'\..*', '', benchmark)]:
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
