import os
from autotest_lib.client.bin import test, autotest_utils
from autotest_lib.client.common_lib import utils


class scrashme(test.test):
    version = 1

    def initialize(self):
        self.job.require_gcc()


    # http://www.codemonkey.org.uk/projects/git-snapshots/scrashme/scrashme-2007-07-08.tar.gz
    def setup(self, tarball = 'scrashme-2007-07-08.tar.gz'):
        tarball = utils.unmap_url(self.bindir, tarball, self.tmpdir)
        autotest_utils.extract_tarball_to_dir(tarball, self.srcdir)
        os.chdir(self.srcdir)
        utils.system('make')


    def execute(self, iterations = 1, args_list = ''):
        if len(args_list) != 0:
            args = '' + args_list
        else:
            args = '-c100 -z'

        profilers = self.job.profilers
        if not profilers.only():
            for i in range(iterations):
                utils.system(self.srcdir + '/scrashme ' + args)

        # Do a profiling run if necessary
        if profilers.present():
            profilers.start(self)
            utils.system(self.srcdir + '/scrashme ' + args)
            profilers.stop(self)
            profilers.report(self)
