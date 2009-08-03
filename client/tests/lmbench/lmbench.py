# This will need more work on the configuration stuff before it will function
import os
from autotest_lib.client.bin import test, utils


class lmbench(test.test):
    version = 2

    def initialize(self):
        self.job.require_gcc()


    def setup(self, tarball = 'lmbench3.tar.bz2'):
        tarball = utils.unmap_url(self.bindir, tarball, self.tmpdir)
        # http://www.bitmover.com/lm/lmbench/lmbench3.tar.gz
        # + lmbench3.diff
        #       removes Makefile references to bitkeeper
        #       default mail to no, fix job placement defaults (masouds)
        utils.extract_tarball_to_dir(tarball, self.srcdir)
        os.chdir(self.srcdir)
        utils.system('make')


    def run_once(self, mem='', fastmem='NO', slowfs='NO', disks='',
                disks_desc='', mhz='', remote='', enough='5000',
                sync_max='1', fsdir=None, file=None):
        if not fsdir:
            fsdir = self.tmpdir
        if not file:
            file = self.tmpdir + 'XXX'

        os.chdir(self.srcdir)
        cmd = "yes '' | make rerun"
        utils.system(cmd)


    def postprocess(self):
        # Get the results:
        outputdir = self.srcdir + "/results"
        results = self.resultsdir + "/summary.txt"
        utils.system("make -C " + outputdir + " summary > " + results)
