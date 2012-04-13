# This will need more work on the configuration stuff before it will function
import os
from autotest.client import test, utils
from autotest.client.common_lib import error


class lmbench(test.test):
    version = 4

    def initialize(self):
        self.job.require_gcc()


    def setup(self, tarball = 'lmbench3.tar.bz2', fsdir=None, file=None):
        """
        Uncompresses the original lmbench tarball, applies a patch to fix
        some build issues, configures lmbench and then modifies the config
        files to use appropriate directory and file locations.

        @param tarball: Lmbench tarball.
        @param fsdir: Directory where file system tests will run
                (defaults to standard test temp dir).
        @param file: Path to the file lmbench will use for status output
                (defaults to a random named file inside standard test temp dir).
        @see: http://www.bitmover.com/lm/lmbench/lmbench3.tar.gz
                (original tarball, shipped as is in autotest).
        """
        tarball = utils.unmap_url(self.bindir, tarball, self.tmpdir)
        utils.extract_tarball_to_dir(tarball, self.srcdir)
        os.chdir(self.srcdir)
        p1 = 'patch -p1 < ../0001-Fix-build-issues-with-lmbench.patch'
        p2 = 'patch -p1 < ../0002-Changing-shebangs-on-lmbench-scripts.patch'
        p3 = 'patch -p1 < ../0003-makefile.patch'
        utils.system(p1)
        utils.system(p2)
        utils.system(p3)

        # build lmbench
        utils.make()

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
        utils.make('rerun')


    def postprocess(self):
        # Get the results:
        outputdir = self.srcdir + "/results"
        results = self.resultsdir + "/summary.txt"
        utils.make("-C " + outputdir + " summary > " + results)
