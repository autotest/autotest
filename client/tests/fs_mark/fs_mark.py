import os
from autotest_lib.client.bin import test, utils


class fs_mark(test.test):
    version = 1

    def initialize(self):
        self.job.require_gcc()


    # http://developer.osdl.org/dev/doubt/fs_mark/archive/fs_mark-3.2.tgz
    def setup(self, tarball = 'fs_mark-3.2.tgz'):
        tarball = utils.unmap_url(self.bindir, tarball, self.tmpdir)
        utils.extract_tarball_to_dir(tarball, self.srcdir)
        os.chdir(self.srcdir)

        utils.system('make')


    def run_once(self, dir, args = None):
        if not args:
            # Just provide a sample run parameters
            args = '-s 10240 -n 1000'
        os.chdir(self.srcdir)
        utils.system('./fs_mark -d %s %s' %(dir, args))
