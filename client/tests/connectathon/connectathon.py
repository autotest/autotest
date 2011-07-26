import os, shutil, glob, logging
from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import error


class connectathon(test.test):
    """
    Connectathon test is an nfs testsuite which can run on
    both BSD and System V based systems. The tests.init file
    has to be modified based on the OS in which this test is run.

    The tar file in this dir has an init file which works for Linux
    platform.

    @see www.connectathon.org
    @author Poornima.Nayak (Poornima.Nayak@in.ibm.com)(original code)
    """
    version = 1
    def initialize(self):
        """
        Sets the overall failure counter for the test.
        """
        self.nfail = 0


    def setup(self, tarball='connectathon.tar.bz2'):
        connectathon_tarball = utils.unmap_url(self.bindir, tarball,
                                               self.tmpdir)
        utils.extract_tarball_to_dir(connectathon_tarball, self.srcdir)

        os.chdir(self.srcdir)
        utils.system('make clean')
        utils.system('make')


    def run_once(self, testdir=None, args='', cthon_iterations=1):
        """
        Runs the test, with the appropriate control file.
        """
        os.chdir(self.srcdir)

        if testdir is None:
            testdir = self.tmpdir

        self.results_path = os.path.join(self.resultsdir,
                                         'raw_output_%s' % self.iteration)

        try:
            if not args:
                # run basic test
                args = "-b -t"

            self.results = utils.system_output('./runtests -N %s %s %s' %
                                              (cthon_iterations, args, testdir))
            utils.open_write_close(self.results_path, self.results)

        except error.CmdError, e:
            self.nfail += 1
            logging.error("Test failed: %s", e)


    def postprocess(self):
        """
        Raises on failure.
        """
        if self.nfail != 0:
            raise error.TestFail('Connectathon test suite failed.')
