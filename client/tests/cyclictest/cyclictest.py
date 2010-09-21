import os
from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import utils


class cyclictest(test.test):
    version = 2
    preserve_srcdir = True

    # git://git.kernel.org/pub/scm/linux/kernel/git/tglx/rt-tests.git
    def initialize(self):
        self.job.require_gcc()


    def setup(self):
        os.chdir(self.srcdir)
        utils.make()


    def execute(self, args = '-t 10 -l 100000'):
        utils.system(self.srcdir + '/cyclictest ' + args)
