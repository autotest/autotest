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


# dictionary used simply for fast lookups
field_dict = {
	'kernel': 'kernel_printable',
	'hostname': 'machine_hostname',
	'test': 'test',
	'label': 'job_label',
	'machine_group': 'machine_group',
	'reason': 'reason',
	'tag': 'job_tag',
	'user': 'job_username',
	'status': 'status_word',
}

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
	if field_input and field_input in field_dict:
		return field_input
	return field_default


def parse_condition(form, form_field, field_default):
	if not form_field in form:
		return field_default
	return form[form_field].value


form = cgi.FieldStorage()
row_field = parse_field(form, 'rows', 'kernel')
column_field = parse_field(form, 'columns', 'machine_group')
condition_field = parse_condition(form, 'condition', '')

cgitb.enable()
db = db.db()


def get_value(test, field):
	if field == 'kernel':
		return test.kernel_printable
	if field == 'hostname':
		return test.machine_hostname
	if field == 'test':
		return test.testname
	if field == 'label':
		return test.job_label
	if field == 'machine_group':
		return test.machine_group
	if field == 'reason':
		return test.reason
	raise "Unknown field"


def construct_link(row_val, column_val):
	next_row = row_field
	next_column = column_field
	condition_list = []
	if condition_field != '':
		condition_list.append(condition_field)
	if row_val:
		next_row = next_field[row_field]
		condition_list.append("%s='%s'" % (row_field, row_val))
	if column_val:
		next_column = next_field[column_field]
		condition_list.append("%s='%s'" % (column_field, column_val))
	next_condition = '&'.join(condition_list)
	return 'compose_query.cgi?' + urllib.urlencode({'columns': next_column,
	           'rows': next_row, 'condition': next_condition})


def create_select_options(selected_val):
	ret = ""

	for option in sorted(field_dict.keys()):
		if selected_val == option:
			selected = " SELECTED"
		else:
			selected = ""

		ret += '<OPTION VALUE="%s"%s>%s</OPTION>\n' % (option, 
		                                               selected,
		                                               option)

	return ret


def smart_sort(list, field):
	if field == 'kernel':
		def kernel_encode(kernel):
		        return kernel_versions.version_encode(kernel) 
		list.sort(key = kernel_encode, reverse = True)
	else:
		list.sort()


def gen_matrix():
	display.print_main_header()

	where = None
	if condition_field.strip() != '':
		where = query_lib.parse_scrub_and_gen_condition(
		            condition_field, field_dict)
		print "<!-- where clause: %s -->" % (where,)

	ret = frontend.get_matrix_data(db, field_dict[column_field],
	                               field_dict[row_field], where)
	(data, column_list, row_list, stat_list, job_tags) = ret

	if not row_list:
		msg = "There are no results for this query (yet?)."
		return [[display.box(msg)]]

	smart_sort(row_list, row_field)
	smart_sort(column_list, column_field)

	link = 'compose_query.cgi?columns=%s&rows=%s&condition=%s' % (
	                row_field, column_field, condition_field)
	header_row = [display.box("<center>(Flip Axis)</center>", link=link)]

	for column in column_list:
		link = construct_link(None, column)
		header_row.append(display.box(column, header=True, link=link))

	matrix = [header_row]
	for row in row_list:
		link = construct_link(row, None)
		cur_row = [display.box(row, header=True, link=link)]
		for column in column_list:
			try:
				box_data = data[column][row]
			except:
				cur_row.append(display.box(None, None))
				continue
			job_tag = job_tags[column][row]
			if job_tag:
				link = '/results/%s/' % job_tag
			else:
				link = construct_link(row, column)
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
	print html_header % (create_select_options(column_field),
	                     create_select_options(row_field),
	                     condition_field)
	display.print_table(gen_matrix())
	print '</body></html>'


main()
