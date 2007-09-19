import os, re, parse, sys, frontend

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


def sort_tests(tests):
	kernel_order = ['patch', 'config', 'build', 'mkinitrd', 'install']

	results = []
	for kernel_op in kernel_order:
		test = 'kernel.' + kernel_op
		if tests.count(test):
			results.append(test)
			tests.remove(test)
	return results + sorted(tests)

