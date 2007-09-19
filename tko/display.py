import os, re, parse, sys, db, frontend
sys.path.insert(0, '/home/mbligh/autotest/client/bin')
import kernel_versions

db = db.db() # db.db(debug=True)

color_map = {
	'GOOD'		: '#66ff66', # green
	'WARN'		: '#fffc00', # yellow
	'FAIL'		: '#ff6666', # red
	'ABORT'		: '#ff6666', # red
	'ERROR'		: '#ff6666', # red
	'NOSTATUS'	: '#ffffff', # white
	'white'		: '#ffffff', # white
	'green'		: '#66ff66', # green
	'yellow'	: '#fffc00', # yellow
	'red'		: '#ff6666', # red
}


class box:
	def __init__(self, data, color_key = None, header = False):
		self.data = data
		if color_map.has_key(color_key):
			self.color = color_map[color_key]
		else:
			self.color = color_map['white']
		self.header = header


	def display(self):
		if self.data:
			data = self.data
		else:
			data = '&nbsp'

		if self.header:
			box_html = 'th'
		else:
			box_html = 'td'

		print "<%s bgcolor=%s>" % (box_html, self.color)
		print data
		print "</%s>" % box_html


def print_table(matrix):
	"""
	matrix: list of lists of boxes, giving a matrix of data
	Each of the inner lists is a row, not a column.

	Display the given matrix of data as a table.
	"""

	print '<table cellpadding=5 border=1 class="boldtable">'
	for row in matrix:
		print '<tr>'
		for element in row:
			print element
			element.display()
		print '</tr>'
	print '</table>'


def kernel_machine_box(kernel, machine):
	status = None
	status_word = ''
	tests = frontend.test.select(db, { 'kernel_idx' : kernel.idx ,
					   'machine' : machine })
	for t in tests:
		if not status or t.status_num < status:
			status = t.status_num
			status_word = db.status_word[status]

	link = 'machine_kernel_test.cgi?machine=%s&kernel=%s' % \
					(machine, kernel.idx)
	if status_word:
		html = '<a href="%s">%s</a>' % (link, status_word)
	else:
		html = None
	return box(html, color_key = status_word)


def kernel_encode(kernel):
	return kernel_versions.version_encode(kernel.printable)


def print_machines_vs_all_kernels(machines):
	header_row = [ box(x, header=True) for x in ['Version'] + machines ] 

	kernels = frontend.kernel.select(db)
	kernels.sort(key = kernel_encode, reverse = True)

	matrix = [header_row]
	for kernel in kernels:
		row = [box(kernel.printable)]
		for machine in machines:
			row.append(kernel_machine_box(kernel, machine))
		matrix.append(row)
	matrix.append(header_row)

	print_table(matrix)


def sort_tests(tests):
	kernel_order = ['patch', 'config', 'build', 'mkinitrd', 'install']

	results = []
	for kernel_op in kernel_order:
		test = 'kernel.' + kernel_op
		if tests.count(test):
			results.append(test)
			tests.remove(test)
	return results + sorted(tests)


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
	test_list = sort_tests(all_tests)

	kernel = frontend.kernel.select(db, {'kernel_idx' : kernel_idx })[0]
	print '<h1>%s</h1>' % kernel.printable

	header_row = [ box(re.sub(r'kernel.', r'kernel<br>', x), header=True)
				for x in ['Version'] + test_list ]
	matrix = [header_row]

	for machine in machines:
		row = [box(machine)]
		for testname in test_list:
			test = results[machine][testname]
			html = '<a href="%s">%s</a>' % \
						(test.url, test.status_word)
			row.append(box(html, color_key = test.status_word))
		matrix.append(row)
	matrix.append(header_row)

	print_table(matrix)

