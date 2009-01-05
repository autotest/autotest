import os
from autotest_lib.client.bin import test, utils


class tiobench(test.test):
    version = 1

    # http://prdownloads.sourceforge.net/tiobench/tiobench-0.3.3.tar.gz
    def setup(self, tarball = 'tiobench-0.3.3.tar.bz2'):
        tarball = utils.unmap_url(self.bindir, tarball, self.tmpdir)
        utils.extract_tarball_to_dir(tarball, self.srcdir)
        os.chdir(self.srcdir)

        utils.system('make')


    def initialize(self):
        self.job.require_gcc()


    def run_once(self, dir = None, args = None):
        if not dir:
            self.dir = self.tmpdir
        else:
            self.dir = dir
        if not args:
            self.args = '--block=4096 --block=8192 --threads=10 --size=1024 --numruns=2'
        else:
            self.args = args

        os.chdir(self.srcdir)
        utils.system('./tiobench.pl --dir %s %s' %(self.dir, self.args))
