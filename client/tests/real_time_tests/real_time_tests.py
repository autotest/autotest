import os
from autotest_lib.client.bin import test, utils

class real_time_tests(test.test):
    version = 1
    preserve_srcdir = True

# http://git.kernel.org/?p=linux/kernel/git/galak/ltp.git;a=tree;f=testcases/realtime
    def setup(self, tarball = 'realtime-latest-git-snapshot.tar.bz2'):
        utils.check_glibc_ver('2.5')
        self.tarball = utils.unmap_url(self.bindir, tarball, self.tmpdir)
        utils.extract_tarball_to_dir(self.tarball, self.srcdir)
        os.chdir(self.srcdir)
        utils.system('patch -p1 < ../path-fix.patch')

    def execute(self, args = '-l 10'):
        os.chdir(self.srcdir)
        utils.system('./run.sh -t func ' + args)
