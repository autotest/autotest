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

import display, frontend, db

cgitb.enable()
db = db.db()

def generate_sql_condition(condition_list):
	""" generate the sql for the condition list."""
	sql = ""
	value = []
	for field, operator, values in condition_list:
		if len(values) == 1:
			sql += " and %s%s%%s" % (field, operator)
			value.append(values[0][0])
		elif len(values) > 1:
			sql += " and "
			expression = [" %s %s %%s" % (field, operator) for val in values]
			for val in values:
				value.append(val[0])
			sql += "(%s)" % " or ".join(expression)
	return sql, value


def prune_list(thelist, condition_sql, condition_value):
	""" keep track of which columns do not have any elements."""
	pruned_list = []
	for g in thelist:
		sql = "t where %s=%%s " % g.idx_name
		value = [g.idx_value]
		sql += condition_sql
		value.extend(condition_value)
		tests = frontend.test.select_sql(db, sql, value)
		if len(tests) > 0:
			pruned_list.append(g)
	return pruned_list


def ParseCondition(condition):
	""" parse the condition into independent clauses."""
	condition_list = []
	if not condition:
		return condition_list
	attribute_re = r"(\w+)"
	op_re = r"(=|!=)"
	value_re = r"('[^']*')"
	# condition is clause & clause & ..
	clause_re = r"%s\s*%s\s*%s" % (attribute_re, op_re, value_re)
	condition_re = re.compile(r"^\s*%s(\s*&\s*%s)*\s*$" % (clause_re, clause_re))
	if not condition_re.match(condition):
		print "Condition not in the correct format: %s" % condition
		sys.exit(0)
	triples = []
	for clause in [c.strip() for c in condition.split('&')]:
		attribute, op, value = re.match(clause_re, clause).groups()
		triples.append((attribute, op, value))
	for (field_name, operator, value) in triples:
		match, field = frontend.select(db, field_name, value)
		if len(match) > 0:
			condition_list.append((field, operator, match))
		else:
			print "No matching records found for condition %s." % \
			      condition
			sys.exit(0)
	return condition_list


def main():

	# parse the fields from the form.
	form = cgi.FieldStorage()
	columns = 'kernel'
	rows = 'test'
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
		condition_list = ParseCondition(condition)
		condition_sql, condition_value = generate_sql_condition(condition_list)

	# get all possible column values.
	column_groups = frontend.anygroup.selectunique(db, columns)

	# get all possible row values.
	row_groups = frontend.anygroup.selectunique(db,rows)
	# keep only those values in rows/columns that have a test
	# corresponding to it.
	row_groups = prune_list(row_groups, condition_sql, condition_value)
	column_groups = prune_list(column_groups, condition_sql, condition_value)

	# prepare the header for the table.
	headers = [g.name for g in column_groups]

	header_row = [display.box(x, header=True) for x in headers]
	header_row.insert(0, display.box("", header=True))

	matrix = [header_row]

	for r_group in row_groups:
		row = [display.box(r_group.name)]
		# get individual unit values
		for c_group in column_groups:
			sql = "t where %s=%%s and %s=%%s" % (r_group.idx_name,
							     c_group.idx_name)
			value = [r_group.idx_value, c_group.idx_value]
			sql += condition_sql
			value.extend(condition_value)
			tests = frontend.test.select_sql(db, sql, value)
			value_str = [str(val) for val in value]
			link = 'test.cgi?sql=%s&values=%s' % \
				(sql, ','.join(value_str))
			row.append(display.status_count_box(db, tests, link))
		matrix.append(row)
	display.print_table(matrix)


main()
