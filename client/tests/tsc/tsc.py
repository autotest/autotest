import os
from autotest_lib.client.bin import test, autotest_utils
from autotest_lib.client.common_lib import utils

class tsc(test.test):
    version = 2
    preserve_srcdir = True

    def setup(self):
        os.chdir(self.srcdir)
        utils.system('make')


    def initialize(self):
        self.job.require_gcc()


    def run_once(self, args = '-t 650'):
        utils.system(self.srcdir + '/checktsc ' + args)
