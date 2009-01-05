import os
from autotest_lib.client.bin import test, utils


class scrashme(test.test):
    version = 1

    def initialize(self):
        self.job.require_gcc()


    # http://www.codemonkey.org.uk/projects/git-snapshots/scrashme/scrashme-2007-07-08.tar.gz
    def setup(self, tarball = 'scrashme-2007-07-08.tar.gz'):
        tarball = utils.unmap_url(self.bindir, tarball, self.tmpdir)
        utils.extract_tarball_to_dir(tarball, self.srcdir)
        os.chdir(self.srcdir)
        utils.system('make')


    def run_once(self, args_list = ''):
        if len(args_list) != 0:
            args = '' + args_list
        else:
            args = '-c100 -z'

        utils.system(self.srcdir + '/scrashme ' + args)
