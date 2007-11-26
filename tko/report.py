#!/usr/bin/python

"""
CLI support to enable user to query the database.
"""

import sys, os, getopt

tko = os.path.dirname(os.path.realpath(os.path.abspath(sys.argv[0])))
sys.path.insert(0, tko)

import query_lib, db, frontend

db = db.db()

help_msg_header = """
NAME
report.py - Print the results matching a given condition in the specified format.

SYNOPSIS
report.py [options]

OPTIONS
"""

help_msg_trailer = """
EXAMPLES
To see every job that has ever been run:
  report.py

To see all the jobs started by johnmacdonald:
  report.py --condition="user='johnmacdonald'"

To see all the jobs started by johnmandonald and on hostname arh22:
  report.py --condition="user='johnmacdonald' & hostname='arh22'"

To see only the test, hostname and user for the reports:
  report.py --columns="test, hostname, user"

You can use both the columns and condition options to generate the kind of report you want.
"""

condition_desc = """Condition to filter the results with.
		  Supported fields are: test, hostname, user, label, machine_group, status, reason, kernel.
		  Supported operators are =, != and string values must be quoted within single quotes.
"""

columns_desc = """Specific columns to display in the results.
		  Supported fields are: test, hostname, user, label, machine_group, status, reason, kernel.
"""

help_desc = """Print command help.
"""


class CliError(Exception):
	pass


class InvalidArgsError(CliError):
	def __init__(self, error):
		CliError.__init__(self, 'Unknown arguments: %r\nTry report.py --help' % error)


class InvalidColumnValue(CliError):
	def __init__(self, error):
		CliError.__init__(self, 'Unrecognized column value: %r\nTry report.py --help' % error)


class cli:
	def __init__(self):
		self.__options = {}


	def add_option(self, name=None, short_name=None, type=None,
		      description=None, value=None):
		""" Adds the options to the cli.
		"""
		if not name and not short_name:
			raise Error("No name provided for the option.")

		short = False

		if not name and short_name:
			short = True
			name = short_name

		self.__options[name] = dict(name=name, type=type,
				            description=description,
					    value=value, short=short)


	def list_options(self):
		""" Return the options for this cli.
		"""
		return self.__options


	def parse_options(self, args):
		""" Parse the options and the values the cli is invoked with.
		"""
		short_opts = ""
		long_opts = []
		for name,val in self.__options.items():
			if val['short']:
				short_opts += val['name']
				if val['type'] != 'bool':
					short_opts += ':'
			else:
				opt = val['name']
				if val['type'] != 'bool':
					opt += '='
				long_opts.append(opt)

		opts, args = getopt.getopt(args[1:], short_opts, long_opts)
		return opts, args


	def usage(self):
		""" Help for the cli.
		"""
		msg = help_msg_header
		for opt,value in self.__options.items():
			if value['short']:
				msg += '-'
			else:
				msg += '--'
			msg += '%s \t: %s\n' % (value['name'], value['description'])

		msg += help_msg_trailer
		return msg


def pretty_print(header, results):
	""" pretty prints the result with all the proper space indentations.
	"""
	# add an extra column for the record number.
	header.insert(0, ' # ')

	# add the record number to each result.
	for j in xrange(len(results)):
		results[j].insert(0, "[%d]" % (j+1))

	# number of columns in the results table.
	size = len(header)

	# list containing the max width of each column.
	column_width = [len(col_name) for col_name in header]

	# update the column width based on the values in the table.
	for record in results:
		for i in xrange(size):
			column_width[i] = max(column_width[i], len(record[i]))

	# Generates the header.
	lines = []
	lines.append('  '.join([header[i].capitalize().ljust(column_width[i])
						     for i in xrange(size)]))
	lines.append('  '.join(['-' * c_size for c_size in column_width]))

	# Generates the table with the appropriate space indent.
	for record in results:
		lines.append('  '.join([record[i].ljust(column_width[i])
                            	for i in xrange(size)]))

	return '\n'.join(lines)


def main(args):
	cli_obj = cli()

	# Add all the known and acceptable options.
	cli_obj.add_option(name='condition', type='string',
			description=condition_desc)
	cli_obj.add_option(name='columns', type='string',
			description=columns_desc)
	cli_obj.add_option(name='help', type='bool',
			  description=help_desc)

	# Parse the options.
	opts,args = cli_obj.parse_options(args)

	# unexpected argument.
	if args:
		raise InvalidArgsError(args)

	sql = None
	value = None

	# by default display these columns
	requested_columns = ['test', 'hostname', 'status', 'reason']

	for option, value in opts:
		if option == '--help':
			print cli_obj.usage()
			return
		elif option == '--condition':
			condition_list = query_lib.parse_condition(value.strip('"'))
			sql, value = query_lib.generate_sql_condition(condition_list)
		elif option == '--columns':
			supported_columns = ['test', 'hostname', 'user', 'label',
					     'machine_group', 'status', 'reason', 'kernel']
			requested_columns = [x.strip() for x in value.split(',')]
			for col in requested_columns:
				if col not in supported_columns:
					raise InvalidColumnValue, 'Unknown field %s specified in the columns option' % col

	# get the values corresponding to the index fields.
	col_values = {}
	for col in requested_columns:
		if col != 'test' and col != 'status' and col != 'reason':
			# the rest of the columns need the index values.
			col_group = frontend.anygroup.selectunique(db, col)
			col_value, field_name = frontend.select(db, col)
			col_values[col] = list(col_value)

	# get all the tests that satisfy the given conditions.
	tests = query_lib.get_tests(sql, value)

	# accumulate the fields that are of interest to the user.
	result = []

	for test in tests:
		record = []

		test_values = {}
		test_values['hostname'] = test.machine_idx
		test_values['user'] = test.job.job_idx
		test_values['label'] = test.job.job_idx
		test_values['machine_group'] = test.machine_idx
		test_values['kernel'] = test.kernel_idx

		for col in requested_columns:
			if col == 'test':
				record.append(test.testname)
			elif col == 'status':
				record.append(test.status_word)
			elif col == 'reason':
				record.append(test.reason.strip())
			else:
				column = col_values[col]
				found = False
				for idx_name, idx_value in column:
					if idx_value == test_values[col]:
						record.append(idx_name)
						found = True
						break
				if not found:
					record.append('')
		result.append(record)

	# generate the pretty table.
	print pretty_print(requested_columns, result)


main(sys.argv)
