import os
from autotest_lib.client.bin import test, utils


class fsstress(test.test):
    version = 1

    def initialize(self):
        self.job.require_gcc()


    # http://www.zip.com.au/~akpm/linux/patches/stuff/ext3-tools.tar.gz
    def setup(self, tarball = 'ext3-tools.tar.gz'):
        self.tarball = utils.unmap_url(self.bindir, tarball, self.tmpdir)
        utils.extract_tarball_to_dir(self.tarball, self.srcdir)

        os.chdir(self.srcdir)
        utils.system('patch -p1 < ../fsstress-ltp.patch')
        utils.system('patch -p1 < ../makefile.patch')
        utils.make('fsstress')


    def run_once(self, testdir = None, extra_args = '', nproc = '1000', nops = '1000'):
        if not testdir:
            testdir = self.tmpdir

        args = '-d %s -p %s -n %s %s' % (testdir, nproc, nops, extra_args)
        cmd = self.srcdir + '/fsstress ' + args
        utils.system(cmd)
