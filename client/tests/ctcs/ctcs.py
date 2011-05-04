import os, shutil, glob, logging
from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import error


class ctcs(test.test):
    """
    This autotest module runs CTCS (Cerberus Test Control System), that is being
    maintained on a new location, since both CTCS and CTCS2 on sourceforge
    were abandoned.

    The original test suite (Cerberus Test Control System) was developed for
    the now extinct VA Linux's manufacturing system it has several hardware
    and software stress tests that can be run in parallel. It does have a
    control file system that allows testers to specify the sorts of tests that
    they want to see executed. It's an excelent stress test for hardware and
    kernel.

    @author Manas Kumar Nayak (maknayak@in.ibm.com) (original code)
    @author Lucas Meneghel Rodrigues (lucasmr@br.ibm.com) (rewrite - ctcs)
    @author Cao, Chen (kcao@redhat.com) (use ctcs2 and port it to 64)
    @author Lucas Meneghel Rodrigues (lmr@redhat.com) (use ctcs new source repo)
    @see: https://github.com/autotest/ctcs
    """
    version = 3

    def initialize(self):
        """
        Sets the overall failure counter for the test.
        """
        self.nfail = 0


    def setup(self, tarball='ctcs.tar.bz2', length='4h', tc_opt='-k',
              tcf_contents=None):
        """
        Builds the test suite, and sets up the control file that is going to
        be processed by the ctcs engine.
        @param tarball: CTCS tarball
        @param length: The amount of time we'll run the test suite
        @param tcf_contents: If the user wants to specify the contents of
                the CTCS control file, he could do so trough this parameter.
                If this parameter is provided, length is ignored.
        """
        ctcs_tarball = utils.unmap_url(self.bindir, tarball, self.tmpdir)
        utils.extract_tarball_to_dir(ctcs_tarball, self.srcdir)

        os.chdir(self.srcdir)
        utils.make()

        # Here we define the cerberus suite control file that will be used.
        # It will be kept on the debug directory for further analysis.
        self.tcf_path = os.path.join(self.debugdir, 'autotest.tcf')

        if not tcf_contents:
            logging.info('Generating CTCS control file')
            # Note about the control file generation command - we are creating
            # a control file with the default tests, except for the kernel
            # compilation test (flag -k).
            g_cmd = ('./newburn-generator %s %s> %s' %
                     (tc_opt, length, self.tcf_path))
            utils.system(g_cmd)
        else:
            logging.debug('TCF file contents supplied, ignoring test length'
                          ' altogether')
            tcf = open(self.tcf_path, 'w')
            tcf.write(tcf_contents)

        logging.debug('Contents of the control file that will be passed to '
                      'CTCS:')
        tcf = open(self.tcf_path, 'r')
        buf = tcf.read()
        logging.debug(buf)


    def run_once(self):
        """
        Runs the test, with the appropriate control file.
        """
        os.chdir(self.srcdir)
        try:
            utils.system('./run %s' % self.tcf_path)
        except:
            self.nfail += 1
        log_base_path = os.path.join(self.srcdir, 'log')
        log_dir = glob.glob(os.path.join(log_base_path,
                                         'autotest.tcf.log.*'))[0]
        logging.debug('Copying %s log directory to results dir', log_dir)
        dst = os.path.join(self.resultsdir, os.path.basename(log_dir))
        shutil.move(log_dir, dst)


    def cleanup(self):
        """
        Cleans up source directory and raises on failure.
        """
        if os.path.isdir(self.srcdir):
            shutil.rmtree(self.srcdir)
        if self.nfail != 0:
            raise error.TestFail('CTCS execution failed')
