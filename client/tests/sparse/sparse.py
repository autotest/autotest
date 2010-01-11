import os
from autotest_lib.client.bin import test, utils, kernel


class sparse(test.test):
    version = 1

    def initialize(self):
        self.job.require_gcc()


    # http://www.codemonkey.org.uk/projects/git-snapshots/sparse/sparse-2006-04-28.tar.gz
    def setup(self, tarball = 'sparse-2006-04-28.tar.gz'):
        tarball = utils.unmap_url(self.bindir, tarball, self.tmpdir)
        utils.extract_tarball_to_dir(tarball, self.srcdir)
        os.chdir(self.srcdir)

        utils.system('make')
        utils.system('ln check sparse')

        self.top_dir = self.job.tmpdir+'/sparse'


    def execute(self, base_tree, patches, config, config_list = None):
        kernel = self.job.kernel(base_tree, self.resultsdir)
        kernel.patch(patches)
        kernel.config(config, config_list)

        os.environ['PATH'] = self.srcdir + ':' + os.environ['PATH']
        results = os.path.join (self.resultsdir, 'sparse')
        kernel.build(make_opts = 'C=1', logfile = results)
