import os, re, parse, sys, db, frontend
sys.path.insert(0, '/home/mbligh/autotest/client/bin')
import kernel_versions

db = db.db() # db.db(debug=True)


def print_kernel_machine(kernel, machine):
	status = None
	status_word = ''
	tests = frontend.test.select(db, { 'kernel_idx' : kernel.idx ,
				  'machine' : machine })
	for t in tests:
		if not status or t.status_num < status:
			status = t.status_num
			status_word = db.status_word[status]
	# lines = ['%s %s<br>' % (t.subdir, t.status_word) for t in tests]
	# print_colored_box(status_word, '\n'.join(lines))
	link = 'machine_kernel_test.cgi?machine=%s&kernel=%s' % \
					(machine, kernel.idx)
	if status_word:
		html = '<a href="%s">%s</a>' % (link, status_word)
	else:
		html = None
	print_colored_box(status_word, html)


def print_colored_box(status, html):
	if not html:
		html = '&nbsp'
	print "<td bgcolor=%s>" % frontend.status_colour[status]
	print html
	print "</td>"


def print_machines_row(machines):
	print "<tr>"
	print "<th>Version</th>"
	for machine in machines:
		print "<th>%s</th>" % machine
	print "</tr>"
	print ""


def kernel_encode(kernel):
	return kernel_versions.version_encode(kernel.printable)


def print_machine_vs_kernel(machines):
	print '<table cellpadding=5 border=1 class="boldtable">'
	print_machines_row(machines)

	kernels = frontend.kernel.select(db)
	kernels.sort(key = kernel_encode, reverse = True)
	for kernel in kernels:
		print "<tr>"
		print "<td>%s</td>" % kernel.printable
		for machine in machines:
			print_kernel_machine(kernel, machine)
		print "</tr>"
		print ""

	print_machines_row(machines)
	print "</table>"


def print_kernel_machines_vs_test(machines, kernel_idx, html_root):
	# first we have to get a list of all run tests across all machines
	all_tests = {}
	all_kernel = {}
	results = {}
	for machine in machines:
		where = { 'kernel_idx' : kernel_idx , 'machine' : machine }
		tests = frontend.test.select(db, where)
		test_dict = {}
		for test in tests:
			if test.subdir.startswith('kernel.'):
				all_kernel[test.subdir] = True
			else:
				all_tests[test.subdir] = True
			test_dict[test.subdir] = test
		results[machine] = test_dict
	test_list = sorted(all_kernel.keys()) + sorted(all_tests.keys())

	kernel = frontend.kernel.select(db, {'kernel_idx' : kernel_idx })[0]
	print '<h1>%s</h1>' % kernel.printable

	print '<table cellpadding=5 border=1 class="boldtable">'
	# First let's get the header row
	print "<tr>"
	print "<td></td>"
	for testname in test_list:
		print "<td>%s</td>" % testname
	print "</tr>"

	for machine in machines:
		print "\n<tr>"
		print "<td>%s</td>" % machine
		for testname in test_list:
			test = results[machine][testname]
			html = '<a href="%s">%s</a>' % \
						(test.url, test.status_word)
			print_colored_box(test.status_word, html)
		print "</tr>"
	print '</table>'
