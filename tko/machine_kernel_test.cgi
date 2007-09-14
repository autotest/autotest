#!/usr/bin/python

import cgi, cgitb, os, sys

tko = '/home/mbligh/autotest/tko'

cgitb.enable()

sys.path.insert(0, tko)
import db
from frontend import *
from display import *

print "Content-type: text/html\n"
form = cgi.FieldStorage()

if not form.has_key("machine") and form.has_key("kernel"):
	raise

machine = form["machine"].value
kernel_version = form["kernel"].value

print_kernel_machines_vs_test([machine], kernel_version)

