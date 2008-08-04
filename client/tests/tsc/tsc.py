import os
from autotest_lib.client.bin import test, autotest_utils
from autotest_lib.client.common_lib import utils

class tsc(test.test):
    version = 1

    def setup(self, tarball = 'checktsc.tar'):
        tarball = utils.unmap_url(self.bindir, tarball, self.tmpdir)
        autotest_utils.extract_tarball_to_dir(tarball, self.srcdir)
        os.chdir(self.srcdir)
        utils.system('make')


    def initialize(self):
        self.job.require_gcc()


    def run_once(self, args = ''):
        utils.system(self.srcdir + '/checktsc ' + args)
