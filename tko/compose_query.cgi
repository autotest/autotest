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
	'test': 'test',
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
## caller can specify rows and columns that shall be included into the report
## regardless of whether actual test data is available yet
force_row_field = parse_condition(form,'force_row','')
force_column_field = parse_condition(form,'force_column','')

def split_forced_fields(force_field):
	if force_field:
		return force_field.split()
	else:
		return []

force_row =  split_forced_fields(force_row_field)
force_column =  split_forced_fields(force_column_field)
  
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


def insert_break_into_kernel_name(kernel_name):
	## insert <br> after each / in kernel name
	## but spare consequtive //
        
	## temporary stubed
	#kernel_name = kernel_name.replace('//',';;')
	#kernel_name = kernel_name.replace('/','/<br>')
	#kernel_name = kernel_name.replace(';;','//')
	return kernel_name


def gen_matrix():
	where = None
	if condition_field.strip() != '':
		where = query_lib.parse_scrub_and_gen_condition(
		            condition_field, frontend.test_view_field_dict)
		print "<!-- where clause: %s -->" % (where,)

	test_data = frontend.get_matrix_data(db, column, row, where)
        
	for f_row in force_row:
		if not f_row in test_data.y_values:
			test_data.y_values.append(f_row)
	for f_column in force_column:
		if not f_column in test_data.x_values:
			test_data.x_values.append(f_column)

	if not test_data.y_values:
		msg = "There are no results for this query (yet?)."
		return [[display.box(msg)]]

	link = 'compose_query.cgi?columns=%s&rows=%s&condition=%s' % (
	                row, column, condition_field)
	header_row = [display.box("<center>(Flip Axis)</center>", link=link)]

	for x in test_data.x_values:
		if column == 'kernel':
			x_br =  insert_break_into_kernel_name(x)
		else:
			x_br = x          
		link = construct_link(x, None)
		header_row.append(display.box(x_br, header=True, link=link))

	matrix = [header_row]
	for y in test_data.y_values:
		if row == 'kernel':
			y_br =  insert_break_into_kernel_name(y)
		else:
			y_br = y
		link = construct_link(None, y)
		cur_row = [display.box(y_br, header=True, link=link)]
		for x in test_data.x_values:
			try:
				box_data = test_data.data[x][y].status_count
			except:
				cur_row.append(display.box(None, None))
				continue
			job_tag = test_data.data[x][y].job_tag
			if job_tag:
				link = '/results/%s/' % job_tag
				if (row == 'test' and
				   not 'boot' in y and
				   not 'build' in y and
				   not 'install' in y ):
					link += y + '/'
				if (column == 'test' and
				   not 'boot' in x and
				   not 'build' in x and
				   not 'install' in x):
					link += x + '/'
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
	print display.color_keys_row()
	display.print_table(gen_matrix())
	print display.color_keys_row()
	print '</body></html>'


main()
