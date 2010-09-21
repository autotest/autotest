# POSIX test suite wrapper class. More information about the suite can be found
# at http://posixtest.sourceforge.net/
import os
from autotest_lib.client.bin import test, utils


__author__ = '''mohd.omar@in.ibm.com (Mohammed Omar)'''

class posixtest(test.test):
    version = 1

    def initialize(self):
        self.job.require_gcc()


    # http://ufpr.dl.sourceforge.net/sourceforge/posixtest/posixtestsuite-1.5.2.tar.gz
    def setup(self, tarball = 'posixtestsuite-1.5.2.tar.gz'):
        self.posix_tarball = utils.unmap_url(self.bindir, tarball, self.tmpdir)
        utils.extract_tarball_to_dir(self.posix_tarball, self.srcdir)
        os.chdir(self.srcdir)
        # Applying a small patch that introduces some linux specific
        # linking options
        utils.system('patch -p1 < ../posix-linux.patch')
        utils.make()


    def execute(self):
        os.chdir(self.srcdir)
        utils.system('./run_tests THR')
