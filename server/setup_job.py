# Copyright 2007 Google Inc. Released under the GPL v2
#
# Eric Li <ericli@google.com>

import logging, os, pickle, shutil, sys
from autotest_lib.client.bin import utils
from autotest_lib.client.common_lib import error, packages


class setup_job(object):
    """This is a new type of job object.

    It is neither inherited from a server_job, nor from client_job. The server
    side job, which is the default job object inside the scope of a test control
    file, has no API to call test.setup() without some significant refactoring
    work, since calling test.setup() is a function of the client job class. But
    in order to simply instantiate a client job object, I need to prepare
    another client job control file, which is not an obvious design either. So I
    designed this setup_job class, which only provides minimum necessary
    functions to call test.setup().

    The setup_job class does not need any job control file at all.
    """
    def __init__(self):
        # inside an autotest client the top autotest dir is autotest/client
        self.autodir = os.environ['AUTODIR']
        self.tmpdir = os.path.join(self.autodir, 'tmp')

        if not os.path.exists(self.tmpdir):
            os.mkdir(self.tmpdir)

        self.pkgmgr = packages.PackageManager(
            self.autodir, run_function_dargs={'timeout':3600})
        self.pkgdir = os.path.join(self.autodir, 'packages')

    # this function is copied from setup_dep() inside client/bin/job.py.
    def setup_dep(self, deps):
      """Set up the dependencies for this test.
      deps is a list of libraries required for this test.
      """
      # Fetch the deps from the repositories and set them up.
      for dep in deps:
          dep_dir = os.path.join(self.autodir, 'deps', dep)
          # Search for the dependency in the repositories if specified,
          # else check locally.
          try:
              if self.pkgmgr.repositories:
                  self.pkgmgr.install_pkg(dep, 'dep', self.pkgdir, dep_dir)
          except error.PackageInstallError:
              # see if the dep is there locally
              pass

          # dep_dir might not exist if it is not fetched from the repos
          if not os.path.exists(dep_dir):
              raise error.TestError("Dependency %s does not exist" % dep)

          os.chdir(dep_dir)
          utils.system('./' + dep + '.py')


def initialize(server_job):
    cwd = os.getcwd()
    os.chdir(server_job.clientdir)
    os.system('tools/make_clean') 
    os.chdir(cwd)

    clientbindir = os.path.join(server_job.clientdir, 'bin')
    sys.path.insert(0, clientbindir)

    os.environ['AUTODIR'] = server_job.clientdir
    os.environ['AUTODIRBIN'] = clientbindir
    os.environ['PYTHONPATH'] = clientbindir


# This function was inspired from runtest() on client/common_lib/test.py.
# Same logic to instantiate a client test object.
def setup_test(testname, resultdir):
    logging.info('setup %s.' % testname)

    local_namespace = locals().copy()
    global_namespace = globals().copy()

    clientdir = os.environ['AUTODIR']
    outputdir = os.path.join(resultdir, testname)
    try:
        os.makedirs(outputdir)
    except OSError, oe:
        print oe

    job = setup_job()
    local_namespace['job'] = job
    local_namespace['outputdir'] = outputdir

    # if the test is local, it can be found in either testdir or site_testdir.
    # tests in site_testdir override tests defined in testdir.
    testdir = os.path.join(clientdir, 'site_tests')
    testbindir = os.path.join(testdir, testname)
    if not os.path.exists(testbindir):
        testdir = os.path.join(clientdir, 'tests')
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

