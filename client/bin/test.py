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

import os, traceback, sys

from autotest_lib.client.common_lib import error, utils
from autotest_lib.client.common_lib import test as common_test
from autotest_lib.client.bin import sysinfo


class test(common_test.base_test):
    pass


def _grab_sysinfo(mytest):
    try:
        sysinfo_dir = os.path.join(mytest.outputdir, 'sysinfo')
        sysinfo.log_after_each_test(sysinfo_dir, mytest.job.sysinfodir)
        sysinfo.log_test_keyvals(mytest, sysinfo_dir)
        if os.path.exists(mytest.tmpdir):
            utils.system('rm -rf ' + mytest.tmpdir)
    except:
        print 'after-test error:'
        traceback.print_exc(file=sys.stdout)


def runtest(job, url, tag, args, dargs):
    common_test.runtest(job, url, tag, args, dargs,
                        locals(), globals(), _grab_sysinfo)
