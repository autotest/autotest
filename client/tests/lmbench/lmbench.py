# This will need more work on the configuration stuff before it will function
import os
from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import error


class lmbench(test.test):
    version = 3

    def initialize(self):
        self.job.require_gcc()


    def setup(self, tarball = 'lmbench3.tar.bz2', fsdir=None, file=None):
        tarball = utils.unmap_url(self.bindir, tarball, self.tmpdir)
        # http://www.bitmover.com/lm/lmbench/lmbench3.tar.gz
        # + lmbench3.diff
        #   - removes Makefile references to bitkeeper
        #   - default mail to no, fix job placement defaults (masouds)
        #   - adds "config" Makefile targets to perform configuration only
        #   - changes scripts/getlist to consider result files that do
        #     not start with "[lmbench 3.x..." (still requires such a line
        #     somewhere in the first 1000 bytes of the file)
        utils.extract_tarball_to_dir(tarball, self.srcdir)
        os.chdir(self.srcdir)

        # build lmbench
        utils.system('make')

        # configure lmbench
        utils.system('yes "" | make config')

        # find the lmbench config file
        config_files = utils.system_output('ls -1 bin/*/CONFIG*').splitlines()
        if len(config_files) != 1:
            raise error.TestError('Failed to find a single lmbench config file,'
                                  ' found: %s' % config_files)
        config_file = config_files[0]

        if not fsdir:
            fsdir = self.tmpdir
        if not file:
            file = os.path.join(self.tmpdir, 'XXX')

        # patch the resulted config to use the proper temporary directory and
        # file locations
        tmp_config_file = config_file + '.tmp'
        utils.system("sed 's!^FSDIR=.*$!FSDIR=%s!' '%s' > '%s'" %
                     (fsdir, config_file, tmp_config_file))
        utils.system("sed 's!^FILE=.*$!FILE=%s!' '%s' > '%s'" %
                     (file, tmp_config_file, config_file))


    def run_once(self):
        os.chdir(self.srcdir)
        utils.system('make rerun')


    def postprocess(self):
        # Get the results:
        outputdir = self.srcdir + "/results"
        results = self.resultsdir + "/summary.txt"
        utils.system("make -C " + outputdir + " summary > " + results)
