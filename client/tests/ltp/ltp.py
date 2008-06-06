import os
from autotest_lib.client.bin import autotest_utils, test
from autotest_lib.client.common_lib import utils, error

class ltp(test.test):
    version = 4

    # http://prdownloads.sourceforge.net/ltp/ltp-full-20080229.tgz
    def setup(self, tarball = 'ltp-full-20080229.tar.bz2'):
        tarball = utils.unmap_url(self.bindir, tarball,
                                           self.tmpdir)
        autotest_utils.extract_tarball_to_dir(tarball, self.srcdir)
        os.chdir(self.srcdir)

        utils.system('patch -p1 < ../ltp.patch')

        # comment the capability tests if we fail to load the capability module
        try:
            utils.system('modprobe capability')
        except error.CmdError, detail:
            utils.system('patch -p1 < ../ltp_capability.patch')

        utils.system('cp ../scan.c pan/')   # saves having lex installed
        utils.system('make -j %d' % autotest_utils.count_cpus())
        utils.system('yes n | make install')


    # Note: to run a specific test, try '-f cmdfile -s test' in the
    # in the args (-f for test file and -s for the test case)
    # eg, job.run_test('ltp', '-f math -s float_bessel')
    def execute(self, args = '', script = 'runltp'):

        # In case the user wants to run another test script
        if script == 'runltp':
            logfile = os.path.join(self.resultsdir, 'ltp.log')
            failcmdfile = os.path.join(self.debugdir, 'failcmdfile')
            args2 = '-q -l %s -C %s -d %s' % (logfile, failcmdfile, self.tmpdir)
            args = args + ' ' + args2

        cmd = os.path.join(self.srcdir, script) + ' ' + args

        profilers = self.job.profilers
        if profilers.present():
            profilers.start(self)
        utils.system(cmd)
        if profilers.present():
            profilers.stop(self)
            profilers.report(self)
