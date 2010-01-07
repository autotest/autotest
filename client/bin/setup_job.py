# Copyright 2007 Google Inc. Released under the GPL v2
#
# Eric Li <ericli@google.com>

import logging, os, pickle, shutil, sys
from autotest_lib.client.bin import utils

def initialize(client_job):
    cwd = os.getcwd()
    os.chdir(client_job.autodir)
    os.system('tools/make_clean') 
    os.chdir(cwd)

    sys.path.insert(0, client_job.bindir)

    os.environ['AUTODIR'] = client_job.autodir
    os.environ['AUTODIRBIN'] = client_job.bindir
    os.environ['PYTHONPATH'] = client_job.bindir


# This function was inspired from runtest() on client/common_lib/test.py.
# Same logic to instantiate a client test object.
def setup_test(testname, client_job):
    logging.info('setup %s.' % testname)

    local_namespace = locals().copy()
    global_namespace = globals().copy()

    outputdir = os.path.join(client_job.resultdir, testname)
    try:
        os.makedirs(outputdir)
    except OSError, oe:
        print oe

    local_namespace['job'] = client_job
    local_namespace['outputdir'] = outputdir

    # if the test is local, it can be found in either testdir or site_testdir.
    # tests in site_testdir override tests defined in testdir.
    testdir = os.path.join(client_job.autodir, 'site_tests')
    testbindir = os.path.join(testdir, testname)
    if not os.path.exists(testbindir):
        testdir = os.path.join(client_job.autodir, 'tests')
        testbindir = os.path.join(testdir, testname)
    local_namespace['testbindir'] = testbindir
    sys.path.insert(0, testbindir)

    try:
        exec("import %s" % testname, local_namespace, global_namespace)
        exec("auto_test = %s.%s(job, testbindir, outputdir)" %
              (testname, testname), local_namespace, global_namespace)
    finally:
        sys.path.pop(0) # pop up testbindir

    pwd = os.getcwd()
    os.chdir(outputdir)

    try:
        auto_test = global_namespace['auto_test']
        auto_test.setup()

        # touch .version file under src to prevent further setup on client host.
        # see client/common_lib/utils.py update_version()
        versionfile = os.path.join(auto_test.srcdir, '.version')
        pickle.dump(auto_test.version, open(versionfile, 'w'))
    finally:
        os.chdir(pwd)
        shutil.rmtree(auto_test.tmpdir, ignore_errors=True)

