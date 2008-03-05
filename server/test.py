# Copyright Martin J. Bligh, Andy Whitcroft, 2007
#
# Define the server-side test class
#

import os

from subcommand import *
from common.error import *
from utils import *

import common.test


class test(common.test.base_test):
	pass


testname = common.test.testname


def runtest(job, url, tag, args, dargs):
	t = subcommand(common.test.runtest,
		       [job, url, tag, args, dargs, locals(), globals()])
	t.fork_start()
	try:
		t.fork_waitfor()
	except AutoservSubcommandError, e:
		raise TestError("Test '%s' failed with exit code %d" %
				(url, e.exit_code))
