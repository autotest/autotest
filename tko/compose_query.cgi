#!/usr/bin/python

"""
Selects all rows and columns that satisfy the condition specified
and draws the matrix. There is a seperate SQL query made for every (x,y)
in the matrix.
"""


print "Content-type: text/html\n"
import cgi, cgitb, re
import sys, os
import urllib 

tko = os.path.dirname(os.path.realpath(os.path.abspath(sys.argv[0])))
sys.path.insert(0, tko)

import display, frontend, db, query_lib
client_bin = os.path.abspath(os.path.join(tko, '../client/bin'))
sys.path.insert(0, client_bin)
import kernel_versions


html_header = """\
<form action="compose_query.cgi" method="get">
<table border="0">
<tr>
  <td>Column: </td>
  <td>Row: </td>
  <td>Condition: </td>
  <td align="center"><a href="index.html">Help</a></td>
</tr>
<tr>
  <td>
  <SELECT NAME="columns">
  %s
 </SELECT>
  </td>
  <td>
  <SELECT NAME="rows">
  %s
  </SELECT>
  </td>
  <td>
    <input type="text" name="condition" size="30" maxlength="200" value="%s">
    <input type="hidden" name="title" value="Report">
  </td>
  <td align="center"><input type="submit" value="Submit">
  </td>
</tr>
</table>
</form>
"""


next_field = {
	'machine_group': 'hostname',
	'hostname': 'tag',
	'tag': 'tag',

	'kernel': 'test',
	'test': 'label',
	'label': 'label',

	'reason': 'reason',
	'user': 'user',
	'status': 'status',
}



def parse_field(form, form_field, field_default):
	if not form_field in form:
		return field_default
	field_input = form[form_field].value.lower()
	if field_input and field_input in frontend.test_view_field_dict:
		return field_input
	return field_default


def parse_condition(form, form_field, field_default):
	if not form_field in form:
		return field_default
	return form[form_field].value


form = cgi.FieldStorage()
row = parse_field(form, 'rows', 'kernel')
column = parse_field(form, 'columns', 'machine_group')
condition_field = parse_condition(form, 'condition', '')

cgitb.enable()
db = db.db()


def construct_link(x, y):
	next_row = row
	next_column = column
	condition_list = []
	if condition_field != '':
		condition_list.append(condition_field)
	if y:
		next_row = next_field[row]
		condition_list.append("%s='%s'" % (row, y))
	if x:
		next_column = next_field[column]
		condition_list.append("%s='%s'" % (column, x))
	next_condition = '&'.join(condition_list)
	return 'compose_query.cgi?' + urllib.urlencode({'columns': next_column,
	           'rows': next_row, 'condition': next_condition})


def create_select_options(selected_val):
	ret = ""

	for option in sorted(frontend.test_view_field_dict.keys()):
		if selected_val == option:
			selected = " SELECTED"
		else:
			selected = ""

		ret += '<OPTION VALUE="%s"%s>%s</OPTION>\n' % \
						(option, selected, option)

	return ret


def gen_matrix():
	where = None
	if condition_field.strip() != '':
		where = query_lib.parse_scrub_and_gen_condition(
		            condition_field, frontend.test_view_field_dict)
		print "<!-- where clause: %s -->" % (where,)

	test_data = frontend.get_matrix_data(db, column, row, where)

	if not test_data.y_values:
		msg = "There are no results for this query (yet?)."
		return [[display.box(msg)]]

	link = 'compose_query.cgi?columns=%s&rows=%s&condition=%s' % (
	                row, column, condition_field)
	header_row = [display.box("<center>(Flip Axis)</center>", link=link)]

	for x in test_data.x_values:
		link = construct_link(x, None)
		header_row.append(display.box(x, header=True, link=link))

	matrix = [header_row]
	for y in test_data.y_values:
		link = construct_link(None, y)
		cur_row = [display.box(y, header=True, link=link)]
		for x in test_data.x_values:
			try:
				box_data = test_data.data[x][y].status_count
			except:
				cur_row.append(display.box(None, None))
				continue
			job_tag = test_data.data[x][y].job_tag
			if job_tag:
				link = '/results/%s/' % job_tag
			else:
				link = construct_link(x, y)
			cur_row.append(display.status_precounted_box(db,
			                                             box_data,
			                                             link))
		matrix.append(cur_row)

	return matrix


def main():
	# create the actual page
	print '<html><head><title>'
	print 'Filtered Autotest Results'
	print '</title></head><body>'
	display.print_main_header()
	print html_header % (create_select_options(column),
	                     create_select_options(row),
	                     condition_field)
	display.print_table(gen_matrix())
	print '</body></html>'


main()
