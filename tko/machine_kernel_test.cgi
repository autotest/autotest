#!/usr/bin/python

import cgi, cgitb, os, sys, re
cgitb.enable()

tko = os.path.dirname(os.path.realpath(os.path.abspath(sys.argv[0])))
sys.path.insert(0, tko)
import db, display, frontend

html_root = 'http://test.kernel.org/google/'
db = db.db()

def main():
	print "Content-type: text/html\n"
	sys.stdout.flush()

	form = cgi.FieldStorage()
	if not form.has_key("machine") and form.has_key("kernel"):
		raise

	machine = form["machine"].value
	kernel_version = form["kernel"].value

	print_kernel_machines_vs_test([machine], kernel_version, html_root)


def print_kernel_machines_vs_test(machines, kernel_idx, html_root):
	# first we have to get a list of all run tests across all machines
	all_tests = []
	results = {}         # will be a 2d hash [machine][testname]
	for machine in machines:
		where = { 'kernel_idx' : kernel_idx , 'machine' : machine }
		tests = frontend.test.select(db, where)
		test_dict = {}
		for test in tests:
			all_tests.append(test.subdir)
			test_dict[test.subdir] = test
		results[machine] = test_dict
	test_list = display.sort_tests(all_tests)

	kernel = frontend.kernel.select(db, {'kernel_idx' : kernel_idx })[0]
	print '<h1>%s</h1>' % kernel.printable

	header_row = [ display.box('Version', header=True) ]
	for test in [re.sub(r'kernel.', r'kernel<br>', x) for x in test_list]:
		header_row.append( display.box(test, header=True) )

	matrix = [header_row]
	for machine in machines:
		row = [display.box(machine)]
		for testname in test_list:
			test = results[machine][testname]
			html = '<a href="%s">%s</a>' % \
						(test.url, test.status_word)
			box = display.box(html, color_key = test.status_word)
			row.append(box)
		matrix.append(row)
	matrix.append(header_row)

	display.print_table(matrix)

main()
