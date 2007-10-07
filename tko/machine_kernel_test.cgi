#!/usr/bin/python
print "Content-type: text/html\n"
import cgi, cgitb, os, sys, re
sys.stdout.flush()
cgitb.enable()

tko = os.path.dirname(os.path.realpath(os.path.abspath(sys.argv[0])))
sys.path.insert(0, tko)
import db, display, frontend

db = db.db()

def main():
	form = cgi.FieldStorage()

	kernel_idx = form['kernel'].value

	if form.has_key('machine'):
		machines = []
		for idx in form['machine'].value.split(','):
			where = { 'machine_idx' : idx }
			machines.append(frontend.machine.select(db, where)[0])
	elif form.has_key('group'):
		where = { 'machine_group' : form['group'].value }
		machines = frontend.machine.select(db, where)

	if form.has_key('test'):
		test = form['test'].value
	else:
		test = None

	kernel = frontend.kernel.select(db, {'kernel_idx' : kernel_idx })[0]
	print_kernel_machines_vs_test(machines, kernel, test)


def print_kernel_machines_vs_test(machines, kernel, only_test):
	# first we have to get a list of all run tests across all machines
	all_tests = []
	results = {}         # will be a 2d hash [machine][testname]
	for machine in machines:
		where = { 'kernel_idx':kernel.idx , 'machine_idx':machine.idx }
		if only_test:
			where['subdir'] = only_test
		tests = frontend.test.select(db, where)
		if not tests:
			continue
		dict = {}
		for test in tests:
			testname = test.testname
			all_tests.append(testname)
			dict[testname] = dict.get(testname, []) + [test]
		results[machine.idx] = dict
	test_list = display.sort_tests(list(set(all_tests)))

	print '<h1>%s</h1>' % kernel.printable

	header_row = [ display.box('Version', header=True) ]
	for test in [re.sub(r'kernel.', r'kernel<br>', x) for x in test_list]:
		header_row.append( display.box(test, header=True) )

	matrix = [header_row]
	for machine in machines:
		if not results.has_key(machine.idx):
			continue
		row = [display.box(machine.hostname)]
		for testname in test_list:
			if results[machine.idx].has_key(testname):
				tests = results[machine.idx][testname]
				# HACK. Link to the first test. Bleh.
				link = tests[0].url
			else:
				tests = []
				link = None
			
			box = display.status_count_box(db, tests, link = link)
			row.append(box)
		matrix.append(row)
	matrix.append(header_row)

	display.print_table(matrix)

main()
