#!/usr/bin/python

"""
Selects all rows and columns that satisfy the condition specified
and draws the matrix. There is a seperate SQL query made for every (x,y)
in the matrix.
"""


print "Content-type: text/html\n"
import cgi, cgitb, re
import sys, os

tko = os.path.dirname(os.path.realpath(os.path.abspath(sys.argv[0])))
sys.path.insert(0, tko)

import display, frontend, db, query_lib

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
    <input type="text" name="condition" size="30" maxlength="80" value="%s">
    <input type="hidden" name="title" value="Report">
  </td>
  <td align="center"><input type="submit" value="Submit">
  </td>
</tr>
</table>
</form>
"""

columns_default = 'kernel'
rows_default = 'test'

cgitb.enable()
db = db.db()

def create_select_options(selected_val, default_val):
	ret = ""
	option_list = ['kernel', 'hostname', 'test', 'label',
	               'machine_group', 'reason']

	if option_list.count(selected_val) == 0:
		selected_val = default_val
	assert(option_list.count(selected_val) > 0)

	for option in option_list:
		if selected_val == option:
			selected = " SELECTED"
		else:
			selected = ""

		ret += '<OPTION VALUE="%s"%s>%s</OPTION>\n' % (option, 
		                                               selected,
		                                               option)

	return ret


def main():
	display.print_main_header()

	# parse the fields from the form.
	form = cgi.FieldStorage()
	columns = columns_default
	rows = rows_default
	condition = None
	for field in form:
		value = form[field].value
		if field == 'columns':
			columns = value
		elif field == 'rows':
			rows = value
		elif field == 'condition':
			condition = value

	# parse the conditions into sql query and value list.
	condition_sql = ""
	condition_value = []
	if condition:
		condition_list = query_lib.parse_condition(condition)
		condition_sql, condition_value =   \
		 query_lib.generate_sql_condition(condition_list)

	# get all possible column values.
	column_groups = frontend.anygroup.selectunique(db, columns)

	# get all possible row values.
	row_groups = frontend.anygroup.selectunique(db,rows)
	# keep only those values in rows/columns that have a test
	# corresponding to it.
	row_groups = query_lib.prune_list(row_groups, condition_sql,  \
					  condition_value)
	column_groups = query_lib.prune_list(column_groups, condition_sql, \
					     condition_value)

	# prepare the header for the table.
	headers = [g.name for g in column_groups]

	header_row = [display.box(x, header=True) for x in headers]
	header_row.insert(0, display.box("", header=True))

	matrix = [header_row]

	# get all the tests that satify the given condition.
	tests = query_lib.get_tests(condition_sql, condition_value)

	for r_group in row_groups:
		row = [display.box(r_group.name)]

		# build the row sql for this row.
		row_expr = [ " %s = %%s " % r_group.idx_name for val in r_group.idx_value]
		row_sql = " (%s) " % " or ".join(row_expr)

		# get individual unit values
		for c_group in column_groups:
			# get the list of tests that belong to this x,y in the matrix.
			xy_test = [test for test in tests
				   if query_lib.get_value(test, r_group.idx_name) \
				   in r_group.idx_value \
				   and query_lib.get_value(test,c_group.idx_name) \
				   in c_group.idx_value]

			# build the column sql
			column_expr = [ " %s = %%s " % c_group.idx_name for val in c_group.idx_value]
			column_sql = " (%s) " % " or ".join(column_expr)

			sql = "t where %s and %s " % (row_sql, column_sql)

			# add the corresponding values of the fields to
			# the value list.

			value = []
			value.extend(r_group.idx_value)
			value.extend(c_group.idx_value)

			# append the condition sql and the values to the
			# sql/list respectively.
			if condition_sql:
				sql += " and "
				sql += condition_sql
				value.extend(condition_value)

			value_str = [str(val) for val in value]
			link = 'test.cgi?sql=%s&values=%s' % \
				(sql, ','.join(value_str))
			row.append(display.status_count_box(db, xy_test, link))
		matrix.append(row)

	# create the actual page
	condition_str = condition
	if condition_str == None:
		condition_str = ""
	print '<html><head><title>'
	print 'Filtered Autotest Results'
	print '</title></head><body>'
	print html_header % (create_select_options(columns, columns_default),
	                     create_select_options(rows, rows_default),
	                     condition_str)
	display.print_table(matrix)
	print '</body></html>'


main()
