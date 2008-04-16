import os, re, sys, frontend

color_map = {
	'header'        : '#e5e5c0', # greyish yellow
	'blank'         : '#ffffff', # white
	'plain_text'    : '#e5e5c0', # greyish yellow
	'borders'       : '#bbbbbb', # grey
	'white'		: '#ffffff', # white
	'green'		: '#66ff66', # green
	'yellow'	: '#fffc00', # yellow
	'red'		: '#ff6666', # red

	#### additional keys for shaded color of a box 
	#### depending on stats of GOOD/FAIL
	'100pct'  : '#80ff80', # green, 94% to 100% of success
	'95pct'   : '#c0ff80', # step twrds yellow, 88% to 94% of success
	'90pct'   : '#ffff80', # yellow, 82% to 88%
	'85pct'   : '#ffc040', # 76% to 82%
	'75pct'   : '#ff4040', # red, 1% to 76%
	'0pct'    : '#d080d0', # violet, <1% of success	

}


def color_keys_row():
	""" Returns one row table with samples of 'NNpct' colors
		defined in the color_map
		and numbers of corresponding %%
	"""
	### This function does not require maintenance in case of	
	### color_map augmenting - as long as 
	### color keys for box shading have names that end with 'pct'
	keys = filter(lambda key: key.endswith('pct'), color_map.keys())
	def num_pct(key):
		return int(key.replace('pct',''))
	keys.sort(key=num_pct)
	html = ''
	for key in keys:
		html+= "\t\t\t<td bgcolor =%s>&nbsp;&nbsp;&nbsp;</td>\n"\
				% color_map[key]
		hint = key.replace('pct',' %')
		if hint[0]<>'0': ## anything but 0 %
			hint = 'to ' + hint
		html+= "\t\t\t<td> %s </td>\n" % hint

	html = """
<table width = "500" border="0" cellpadding="2" cellspacing="2">\n
	<tbody>\n
		<tr>\n
%s
		</tr>\n
	</tbody>
</table><br>
""" % html
	return html


class box:
	def __init__(self, data, color_key = None, header = False, link = None,
		     tooltip = None ):
		if data:
			data = "<tt>%s</tt>" % data
		if link and tooltip:
			self.data = '<a href="%s" title="%s">%s</a>' \
						% (link, tooltip, data)
		elif tooltip:
			self.data = '<a href="%s" title="%s">%s</a>' \
						% ('#', tooltip, data)			
		elif link:
			self.data = '<a href="%s">%s</a>' % (link, data)
		else:
			self.data = data

		if color_map.has_key(color_key):
			self.color = color_map[color_key]
		elif header:
			self.color = color_map['header']
		elif data:
			self.color = color_map['plain_text']
		else:
			self.color = color_map['blank']
		self.header = header


	def html(self):
		if self.data:
			data = self.data
		else:
			data = '&nbsp'

		if self.header:
			box_html = 'th'
		else:
			box_html = 'td'

		return "<%s bgcolor=%s>%s</%s>" % \
					(box_html, self.color, data, box_html)


def grade_from_status(status):
	# % of goodness
	# GOOD (6)  -> 1
	# ##  If the test doesn't PASS, it FAILS
	# else -> 0

	if status == 6:
		return 1.0
	else:
		return 0.0


def average_grade_from_status_count(status_count):
	average_grade = 0
	total_count = 0
	for key in status_count.keys():
		average_grade += grade_from_status(key)*status_count[key]
		total_count += status_count[key]
	average_grade = average_grade / total_count
	return average_grade


def shade_from_status_count(status_count):
	if not status_count:
		return None
	
	## average_grade defines a shade of the box
	## 0 -> violet
	## 0.76 -> red
	## 0.88-> yellow
	## 1.0 -> green	
	average_grade = average_grade_from_status_count(status_count)
	
	## find appropiate keyword from color_map
	if average_grade<0.01:
		shade = '0pct'
	elif average_grade<0.75:
		shade = '75pct'
	elif average_grade<0.85:
		shade = '85pct'
	elif average_grade<0.90:
		shade = '90pct'
	elif average_grade<0.95:
		shade = '95pct'
	else:
		shade = '100pct'
		
	return shade


def status_html(db, box_data, shade):
	"""
	status_count: dict mapping from status (integer key) to count
	eg. { 'GOOD' : 4, 'FAIL' : 1 }
	"""
	status_count = box_data.status_count
	if 6 in status_count.keys():
		html = "%d&nbsp;/&nbsp;%d " \
			%(status_count[6],sum(status_count.values()))
	else:
		html = "%d&nbsp;/&nbsp;%d " % \
			(0, sum(status_count.values()))

	if box_data.reasons_list:
		box_data.reasons_list.sort()
		for reason in box_data.reasons_list:
			reason = reason.replace('<br>','\n')
			reason = reason.replace('<','[').replace('>',']')
			reason = reason.replace('|','\n').replace('&',' AND ')
			reason = reason.replace('\n','<br>')
			html += '<br>' + reason

	tooltip = ""
	for status in sorted(status_count.keys(), reverse = True):
		status_word = db.status_word[status]
		tooltip += "%d %s " % (status_count[status], status_word)
	return (html,tooltip)


def status_count_box(db, tests, link = None):
	"""
	Display a ratio of total number of GOOD tests
	to total number of all tests in the group of tests.
	More info (e.g. 10 GOOD, 2 WARN, 3 FAIL) is in tooltips
	"""
	if not tests:
		return box(None, None)

	status_count = {}
	for test in tests:
		count = status_count.get(test.status_num, 0)
		status_count[test.status_num] = count + 1
	return status_precounted_box(db, status_count, link)


def status_precounted_box(db, box_data, link = None):
	"""
	Display a ratio of total number of GOOD tests
	to total number of all tests in the group of tests.
	More info (e.g. 10 GOOD, 2 WARN, 3 FAIL) is in tooltips
	"""
	status_count = box_data.status_count
	if not status_count:
		return box(None, None)
	
	shade = shade_from_status_count(status_count)	
	html,tooltip = status_html(db, box_data, shade)
	precounted_box = box(html, shade, False, link, tooltip)
	return precounted_box


def print_table(matrix):
	"""
	matrix: list of lists of boxes, giving a matrix of data
	Each of the inner lists is a row, not a column.

	Display the given matrix of data as a table.
	"""

	print '<table bgcolor="%s" cellspacing="1" cellpadding="5">' % (
	    color_map['borders'])
	for row in matrix:
		print '<tr>'
		for element in row:
			print element.html()
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
	if tests.count('boot'):
		results.append('boot')
		tests.remove('boot')
	return results + sorted(tests)


def print_main_header():
	print '<head><style type="text/css">'
	print 'a { text-decoration: none }'
	print '</style></head>'
	print '<h2>'
	print '<a href="compose_query.cgi">Functional</a>'
	print '&nbsp&nbsp&nbsp'
	print '<a href="machine_benchmark.cgi">Performance</a>'
	print '&nbsp&nbsp&nbsp'
	print '<a href="http://test.kernel.org/autotest">[about Autotest]</a>'
	print '</h2><p>'


def group_name(group):
	name = re.sub('_', '<br>', group.name)
	if re.search('/', name):
		(owner, machine) = name.split('/', 1)
		name = owner + '<br>' + machine
	return name
