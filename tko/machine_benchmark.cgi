#!/usr/bin/python

import cgi, cgitb, os, sys, re
cgitb.enable()

tko = os.path.dirname(os.path.realpath(os.path.abspath(sys.argv[0])))
sys.path.insert(0, tko)
import db, display, frontend

html_root = 'http://test.kernel.org/google/'
db = db.db()

benchmark_key = {
'kernbench' : 'elapsed',
'dbench' : 'throughput',
'tbench' : 'throughput',
}

def main():
	print "Content-type: text/html\n"
	sys.stdout.flush()

	rows = db.select('test', 'tests', {}, distinct = True)
	benchmarks = []
	for row in rows:
		benchmark = row[0]
		testname = re.sub(r'\..*', '', benchmark)
		if not benchmark_key.has_key(testname):
			continue
		benchmarks.append(benchmark)
	benchmarks = display.sort_tests(benchmarks)

	machines = frontend.machine.select(db)

	print '<h1>Performance</h1>'

	header_row =  [ display.box('Benchmark', header=True) ]
	header_row += [ display.box(re.sub(r'\.', '<br>', benchmark), header=True) for benchmark in benchmarks ]
	
	matrix = [header_row]
	for machine in machines:
		row = [display.box(machine.hostname)]
		for benchmark in benchmarks:
			where = { 'machine_idx' : machine.idx,
				  'subdir' : benchmark }
			rows = db.select('count(test_idx)', 'tests', where)
			count = rows[0][0]
			if not count:
				row.append(display.box(None))
				continue
			testname = re.sub(r'\..*', '', benchmark)
			url = 'machine_test_attribute_graph.cgi'
			url += '?machine=%s&benchmark=%s&key=%s' % \
				(machine.idx, benchmark, benchmark_key[testname])
			html = '<a href="%s">%d</a>' % (url, count)
			row.append(display.box(html))
		matrix.append(row)
	matrix.append(header_row)

	display.print_table(matrix)

main()
