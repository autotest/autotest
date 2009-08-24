import os
from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import utils


class synctest(test.test):
    version = 1
    preserve_srcdir = True

    def initialize(self):
        self.job.require_gcc()


    def setup(self):
        os.chdir(self.srcdir)
        utils.system('make')


    def run_once(self, len, loop, testdir=None):
        args = len + ' ' + loop
        output = os.path.join(self.srcdir, 'synctest ')
        if testdir:
           os.chdir(testdir)
        utils.system(output + args)
