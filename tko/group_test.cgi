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
	kernel_idx = form["kernel"].value
	kernel = frontend.kernel.select(db, {'kernel_idx' : kernel_idx })[0]
	groups = frontend.group.select(db)

	print_kernel_groups_vs_tests(kernel, groups)


def print_kernel_groups_vs_tests(kernel, groups):
	# first we have to get a list of all run tests across all machines
	all_tests = set()
	results = {}         # will be a 3d hash [group][test][status] = count
	for group in groups:
		results[group] = {}
		for test in group.tests():
			all_tests.add(test.subdir)
			results[group][test.subdir] = {}
			count = results[group][test.subdir].get(test.status_num, 0)
			results[group][test.subdir][test.status_num] = count + 1
	all_tests = list(all_tests)
		
	print '<h1>%s</h1>' % kernel.printable

	header_row = [ display.box('Test', header=True) ]
	for group in groups:
		header_row.append( display.box(group, header=True) )

	matrix = [header_row]
	for testname in all_tests:
		row = [display.box(re.sub(r'kernel.', r'kernel<br>', testname))]
		for group in groups:
			if not results[group].has_key(testname):
				continue
			worst = sorted(results[group][testname].keys())[0]
			html = display.status_html(db, results[group][testname])
			box = display.box(html, db.status_word[worst])
			row.append(box)
		matrix.append(row)
	matrix.append(header_row)

	display.print_table(matrix)

main()
