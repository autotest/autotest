import os
from autotest_lib.client.bin import test, autotest_utils
from autotest_lib.client.common_lib import utils


class interbench(test.test):
    version = 1

    def initialize(self):
        self.job.require_gcc()
        self.iteration = 0


    # http://www.kernel.org/pub/linux/kernel/people/ck/apps/interbench/interbench-0.30.tar.bz2
    def setup(self, tarball = 'interbench-0.30.tar.bz2'):
        tarball = utils.unmap_url(self.bindir, tarball, self.tmpdir)
        autotest_utils.extract_tarball_to_dir(tarball, self.srcdir)
        os.chdir(self.srcdir)
        utils.system('make')


    def run_once(self, args = ''):
        os.chdir(self.tmpdir)
        args += " -c"
        self.iteration += 1
        utils.system("%s/interbench -m 'run #%s' %s" % (self.srcdir, 
                                                        self.iteration, args))
