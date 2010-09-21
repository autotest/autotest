import os, re
from autotest_lib.client.bin import utils, test
from autotest_lib.client.common_lib import error

# test requires at least 2.6.26, will skip otherwise (check is internal)
class perfmon(test.test):
    version = 16

    def setup(self, tarball = 'perfmon-tests-0.3.tar.gz'):
        tarball = utils.unmap_url(self.bindir, tarball, self.tmpdir)
        utils.extract_tarball_to_dir(tarball, self.srcdir)
        os.chdir(self.srcdir)
        utils.make()


    def initialize(self):
        self.job.require_gcc()
        self.results = []


    def run_once(self, dir = None, nprocs = None, args = ''):
        cmd = self.srcdir + '/tests/pfm_tests' + args
        # self.results.append(utils.system_output(cmd, retain_output=True))
        if 'FAIL' in utils.system_output(cmd, retain_output=True):
            raise error.TestError('some perfmon tests failed')
