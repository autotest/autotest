import os
from autotest_lib.client.bin import utils, test
from autotest_lib.client.common_lib import error

class ltp(test.test):
    version = 6

    def _import_site_config(self):
        site_config_path = os.path.join(os.path.dirname(__file__),
                                        'site_config.py')
        if os.path.exists(site_config_path):
            # for some reason __import__ with full path does not work within
            # autotest, although it works just fine on the same client machine
            # in the python interactive shell or separate testcases
            execfile(site_config_path)
            self.site_ignore_tests = locals().get('ignore_tests', [])
        else:
            self.site_ignore_tests = []


    def initialize(self):
        self._import_site_config()
        self.job.require_gcc()


    # http://prdownloads.sourceforge.net/ltp/ltp-full-20091231.tgz
    def setup(self, tarball = 'ltp-full-20091231.tar.bz2'):
        tarball = utils.unmap_url(self.bindir, tarball, self.tmpdir)
        utils.extract_tarball_to_dir(tarball, self.srcdir)
        os.chdir(self.srcdir)
        ltpbin_dir = os.path.join(self.srcdir, 'bin')
        os.mkdir(ltpbin_dir)

        utils.system('patch -p1 < ../ltp.patch')

        # comment the capability tests if we fail to load the capability module
        try:
            utils.system('modprobe capability')
        except error.CmdError, detail:
            utils.system('patch -p1 < ../ltp_capability.patch')

        utils.system('cp ../scan.c pan/')   # saves having lex installed
        utils.configure('--prefix=%s' % ltpbin_dir)
        utils.make('-j %d all' % utils.count_cpus())
        utils.system('yes n | make SKIP_IDCHECK=1 install')


    # Note: to run a specific test, try '-f cmdfile -s test' in the
    # in the args (-f for test file and -s for the test case)
    # eg, job.run_test('ltp', '-f math -s float_bessel')
    def run_once(self, args = '', script = 'runltp', ignore_tests=[]):

        ignore_tests = ignore_tests + self.site_ignore_tests

        # In case the user wants to run another test script
        if script == 'runltp':
            logfile = os.path.join(self.resultsdir, 'ltp.log')
            failcmdfile = os.path.join(self.debugdir, 'failcmdfile')
            args2 = '-q -l %s -C %s -d %s' % (logfile, failcmdfile, self.tmpdir)
            args = args + ' ' + args2

        ltpbin_dir = os.path.join(self.srcdir, 'bin')
        cmd = os.path.join(ltpbin_dir, script) + ' ' + args
        result = utils.run(cmd, ignore_status=True)

        # look for the first line in result.stdout containing FAIL and,
        # if found, raise the whole line as a reason of the test failure.
        for line in result.stdout.split():
            if 'FAIL' in line:
                test_name = line.strip().split(' ')[0]
                if not test_name in ignore_tests:
                    raise error.TestFail(line)
