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


def _get_sysinfo_dirs(mytest):
    """ Returns (job_sysinfo_dir, test_sysinfo_dir) for a given test """
    job_dir = mytest.job.sysinfodir
    test_dir = os.path.join(mytest.outputdir, "sysinfo")
    return job_dir, test_dir


def _prepare_sysinfo(state, mytest):
    try:
        job_dir, test_dir = _get_sysinfo_dirs(mytest)
        sysinfo.log_before_each_test(state, job_dir, test_dir)
    except:
        print "before-test error:"
        traceback.print_exc(file=sys.stdout)


def _grab_sysinfo(state, mytest):
    try:
        job_dir, test_dir = _get_sysinfo_dirs(mytest)
        sysinfo.log_after_each_test(state, job_dir, test_dir)
        sysinfo.log_test_keyvals(mytest, test_dir)
        if os.path.exists(mytest.tmpdir):
            shutil.rmtree(mytest.tmpdir, ignore_errors=True)
    except:
        print "after-test error:"
        traceback.print_exc(file=sys.stdout)


def runtest(job, url, tag, args, dargs):
    state_dict = {}
    before_hook = lambda t: _prepare_sysinfo(state_dict, t)
    after_hook = lambda t: _grab_sysinfo(state_dict, t)
    common_test.runtest(job, url, tag, args, dargs,
                        locals(), globals(), before_hook, after_hook)
