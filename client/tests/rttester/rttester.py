import os
from autotest_lib.client.bin import test, utils, os_dep


class rttester(test.test):
    version = 1

    # http://www.stardust.webpages.pl/files/patches/autotest/rttester.tar.bz2

    def setup(self, tarball = 'rttester.tar.bz2'):
        tarball = utils.unmap_url(self.bindir, tarball, self.tmpdir)
        utils.extract_tarball_to_dir(tarball, self.srcdir)

    def execute(self):
        os.chdir(self.srcdir)
        utils.system(self.srcdir + '/check-all.sh')
