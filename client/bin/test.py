# Copyright Martin J. Bligh, Andy Whitcroft, 2006
#
# Shell class for a test, inherited by all individual tests
#
# Methods:
#	__init__	initialise
#	initialize	run once for each job
#	setup		run once for each new version of the test installed
#	run		run the test (wrapped by job.run_test())
#
# Data:
#	job		backreference to the job this test instance is part of
#	outputdir	eg. results/<job>/<testname.tag>
#	resultsdir	eg. results/<job>/<testname.tag>/results
#	profdir		eg. results/<job>/<testname.tag>/profiling
#	debugdir	eg. results/<job>/<testname.tag>/debug
#	bindir		eg. tests/<test>
#	src		eg. tests/<test>/src
#	tmpdir		eg. tmp/<testname.tag>

import os, traceback

from autotest_utils import *
from common.error import *

import sysinfo
import common.test


class test(common.test.base_test):
	pass


testname = common.test.testname


def _grab_sysinfo(mytest):
	try:
		sysinfo_dir = os.path.join(mytest.outputdir, 'sysinfo')
		sysinfo.log_after_each_test(sysinfo_dir, mytest.job.sysinfodir)
		if os.path.exists(mytest.tmpdir):
			system('rm -rf ' + mytest.tmpdir)
	except:
		print 'after-test error:'
		traceback.print_exc(file=sys.stdout)

def runtest(job, url, tag, args, dargs):
	common.test.runtest(job, url, tag, args, dargs,
			    locals(), globals(), _grab_sysinfo)
