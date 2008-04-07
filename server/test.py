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
	common.test.runtest(job, url, tag, args, dargs,
			    locals(), globals())
