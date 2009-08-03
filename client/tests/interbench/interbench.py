import os
from autotest_lib.client.bin import test, utils


class interbench(test.test):
    version = 1

    def initialize(self):
        self.job.require_gcc()


    # http://www.kernel.org/pub/linux/kernel/people/ck/apps/interbench/interbench-0.30.tar.bz2
    def setup(self, tarball = 'interbench-0.30.tar.bz2'):
        tarball = utils.unmap_url(self.bindir, tarball, self.tmpdir)
        utils.extract_tarball_to_dir(tarball, self.srcdir)
        os.chdir(self.srcdir)
        utils.system('make')


    def run_once(self, args = ''):
        os.chdir(self.tmpdir)
        args += " -c"
        utils.system("%s/interbench -m 'run #%s' %s" % (self.srcdir,
                                                        self.iteration, args))
