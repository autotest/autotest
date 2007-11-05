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
	display.print_main_header()

	form = cgi.FieldStorage()
	kernel_idx = form["kernel"].value
	kernel = frontend.kernel.select(db, {'kernel_idx' : kernel_idx })[0]
	groups = frontend.group.select(db)

	print_kernel_groups_vs_tests(kernel, groups)


def print_kernel_groups_vs_tests(kernel, groups):
	# first we have to get a list of all run tests across all machines
	all_tests = set()
	for group in groups:
		for test in group.tests({ 'kernel_idx' : kernel.idx }):
			all_tests.add(test.subdir)
	all_tests = list(all_tests)
		
	print '<h1>%s</h1>' % kernel.printable

	header_row = [ display.box('Test', header=True) ]
	for group in groups:
		header_row.append( display.box(group.name, header=True) )

	matrix = [header_row]
	for testname in all_tests:
		shortname = re.sub(r'kernel.', r'kernel<br>', testname)
		row = [display.box(shortname)]
		for group in groups:
			tests = group.tests({ 'kernel_idx' : kernel.idx ,
					      'subdir' : testname })
			link = 'machine_kernel_test.cgi?'
			link += 'group=%s&kernel=%s&test=%s' % \
					(group.name, kernel.idx, testname)
			box = display.status_count_box(db, tests, link=link)
			row.append(box)
		matrix.append(row)
	matrix.append(header_row)

	display.print_table(matrix)

main()
