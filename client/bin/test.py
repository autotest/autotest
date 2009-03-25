# Copyright Martin J. Bligh, Andy Whitcroft, 2006
#
# Shell class for a test, inherited by all individual tests
#
# Methods:
#       __init__        initialise
#       initialize      run once for each job
#       setup           run once for each new version of the test installed
#       run             run the test (wrapped by job.run_test())
#
# Data:
#       job             backreference to the job this test instance is part of
#       outputdir       eg. results/<job>/<testname.tag>
#       resultsdir      eg. results/<job>/<testname.tag>/results
#       profdir         eg. results/<job>/<testname.tag>/profiling
#       debugdir        eg. results/<job>/<testname.tag>/debug
#       bindir          eg. tests/<test>
#       src             eg. tests/<test>/src
#       tmpdir          eg. tmp/<testname.tag>

import os, traceback, sys, shutil

from autotest_lib.client.common_lib import error, utils
from autotest_lib.client.common_lib import test as common_test
from autotest_lib.client.bin import sysinfo


class test(common_test.base_test):
    pass


def runtest(job, url, tag, args, dargs):
    common_test.runtest(job, url, tag, args, dargs, locals(), globals(),
                        job.sysinfo.log_before_each_test,
                        job.sysinfo.log_after_each_test,
                        job.sysinfo.log_before_each_iteration,
                        job.sysinfo.log_after_each_iteration)
