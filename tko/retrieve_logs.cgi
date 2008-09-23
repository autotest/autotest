#!/usr/bin/python

import cgi, os, sys

page = """\
Status: 302 Found
Content-Type: text/plain
Location: %s\r\n\r
"""

# Get access to directories
tko = os.path.dirname(os.path.realpath(os.path.abspath(sys.argv[0])))
sys.path.insert(0, tko)

autodir = os.path.abspath(os.path.join(tko, '..'))

# Define function for retrieving logs
try:
	import site_retrieve_logs
	retrieve_logs = site_retrieve_logs.retrieve_logs
	del site_retrieve_logs
except ImportError:
	def retrieve_logs(job_path):
		pass

# Get form fields
form = cgi.FieldStorage(keep_blank_values=True)
# Retrieve logs
job_path = form['job'].value[1:]
job_path = os.path.join(autodir, job_path)
keyval = retrieve_logs(job_path)

# Redirect to results page
testname = ''
if 'test' in form:
	testname = form['test'].value
	full_path = os.path.join(job_path, form['test'].value)
	if not os.path.exists(full_path):
		testname = ''
path = "%s%s" % (form['job'].value, testname)
print page % path
