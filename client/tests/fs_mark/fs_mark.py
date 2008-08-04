import os
from autotest_lib.client.bin import test, autotest_utils
from autotest_lib.client.common_lib import utils


class fs_mark(test.test):
    version = 1

    def initialize(self):
        self.job.require_gcc()


    # http://developer.osdl.org/dev/doubt/fs_mark/archive/fs_mark-3.2.tgz
    def setup(self, tarball = 'fs_mark-3.2.tgz'):
        tarball = utils.unmap_url(self.bindir, tarball, self.tmpdir)
        autotest_utils.extract_tarball_to_dir(tarball, self.srcdir)
        os.chdir(self.srcdir)

        utils.system('make')


    def execute(self, dir, iterations = 2, args = None):
        os.chdir(self.srcdir)
        if not args:
            # Just provide a sample run parameters
            args = '-s 10240 -n 1000'
        profilers = self.job.profilers
        if not profilers.only():
            for i in range(iterations):
                utils.system('./fs_mark -d %s %s' %(dir, args))

        # Do a profiling run if necessary
        if profilers.present():
            profilers.start(self)
            utils.system('./fs_mark -d %s %s' %(dir, args))
            profilers.stop(self)
            profilers.report(self)
