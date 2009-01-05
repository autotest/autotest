import os
from autotest_lib.client.bin import test, utils


class pi_tests(test.test):
    version = 1

    def initialize(self):
        self.job.require_gcc()


    # http://www.stardust.webpages.pl/files/patches/autotest/pi_tests.tar.bz2
    def setup(self, tarball = 'pi_tests.tar.bz2'):
        utils.check_glibc_ver('2.5')
        tarball = utils.unmap_url(self.bindir, tarball, self.tmpdir)
        utils.extract_tarball_to_dir(tarball, self.srcdir)
        os.chdir(self.srcdir)
        utils.system('make')


    def execute(self, args = '1 300'):
        os.chdir(self.srcdir)
        utils.system('./start.sh ' + args)
