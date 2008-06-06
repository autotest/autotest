import os
from autotest_lib.client.bin import test, autotest_utils
from autotest_lib.client.common_lib import utils


class fsfuzzer(test.test):
    version = 1

    # http://people.redhat.com/sgrubb/files/fsfuzzer-0.6.tar.gz
    def setup(self, tarball = 'fsfuzzer-0.6.tar.gz'):
        tarball = utils.unmap_url(self.bindir, tarball,
                                           self.tmpdir)
        autotest_utils.extract_tarball_to_dir(tarball, self.srcdir)
        os.chdir(self.srcdir)

        utils.system('make')

    def execute(self, iterations = 1, fstype = 'iso9660'):
        profilers = self.job.profilers
        args = fstype + ' 1'
        if not profilers.only():
            for i in range(iterations):
                utils.system(self.srcdir + '/run_test ' + args)

        # Do a profiling run if necessary
        if profilers.present():
            profilers.start(self)
            utils.system(self.srcdir + '/run_test ' + args)
            profilers.stop(self)
            profilers.report(self)
