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
	machine_idxs = form["machine"].value
	kernel_idx = form["kernel"].value

	kernel = frontend.kernel.select(db, {'kernel_idx' : kernel_idx })[0]
	machines = []
	for idx in machine_idxs.split(','):
		machine = frontend.machine.select(db, {'machine_idx' : idx})[0]
		machines.append(machine)
	print_kernel_machines_vs_test(machines, kernel)


def print_kernel_machines_vs_test(machines, kernel):
	# first we have to get a list of all run tests across all machines
	all_tests = []
	results = {}         # will be a 2d hash [machine][testname]
	for machine in machines:
		where = { 'kernel_idx':kernel.idx , 'machine_idx':machine.idx }
		tests = frontend.test.select(db, where)
		if not tests:
			continue
		test_dict = {}
		for test in tests:
			all_tests.append(test.testname)
			test_dict[test.testname] = test
		# FIXME. What happens on multiple counts of the same test?
		# ie. we run two identical jobs on the same machine ...
		results[machine.idx] = test_dict
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
			if not results[machine.idx].has_key(testname):
				continue
			test = results[machine.idx][testname]
			box = display.box(test.status_word,
				color_key = test.status_word, link = test.url)
			row.append(box)
		matrix.append(row)
	matrix.append(header_row)

	display.print_table(matrix)

main()
