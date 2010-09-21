import os, shutil, re
from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import error


class systemtap(test.test):
    """
    This autotest module runs the systemtap test suite.

        @author Anton Blanchard <anton@au.ibm.com>
    """

    version = 1
    def initialize(self, local=False):
        self.job.require_gcc()

        self.systemtap_dir = ''
        if local == False:
            self.systemtap_dir = os.path.join(self.autodir,
                'deps/systemtap/systemtap')

    def setup(self, local=False, tarball_systemtap='systemtap-0.9.5.tar.gz', tarball_elfutils='elfutils-0.140.tar.bz2'):
        depdir = os.path.join(self.autodir, 'deps/systemtap')
        tarball_systemtap = utils.unmap_url(depdir, tarball_systemtap, self.tmpdir)
        tarball_elfutils = utils.unmap_url(depdir, tarball_elfutils, self.tmpdir)
        srcdir = os.path.join(depdir, 'src')
        utils.extract_tarball_to_dir(tarball_systemtap, srcdir)
        elfdir = os.path.join(srcdir, 'elfutils')
        utils.extract_tarball_to_dir(tarball_elfutils, elfdir)

        self.job.setup_dep(['dejagnu'])
        if local == False:
            self.job.setup_dep(['systemtap'])

        # Try grabbing the systemtap tarball out of the deps directory
        depdir = os.path.join(self.autodir, 'deps/systemtap')
        if os.path.exists(os.path.join(depdir, tarball_systemtap)):
            tarball = utils.unmap_url(depdir, tarball_systemtap, self.tmpdir)
        else:
            tarball = utils.unmap_url(self.bindir, tarball_systemtap, self.tmpdir)
        utils.extract_tarball_to_dir(tarball_systemtap, self.srcdir)

        testsuite = os.path.join(self.srcdir, 'testsuite')
        os.chdir(testsuite)

        utils.configure()
        utils.make()

        # Run a simple systemtap script to make sure systemtap and the
        # kernel debuginfo packages are correctly installed
        script = "PATH=%s/bin:$PATH stap -c /bin/true -e 'probe syscall.read { exit() }'" % self.systemtap_dir
        try:
            utils.system(script)
        except:
            raise error.TestError('simple systemtap test failed, kernel debuginfo package may be missing: %s' % script)


    def run_once(self):
        testsuite = os.path.join(self.srcdir, 'testsuite')
        os.chdir(testsuite)

        dejagnu_dir = os.path.join(self.autodir, 'deps/dejagnu/dejagnu')

        utils.system('PATH=%s/bin:%s/bin:$PATH make installcheck' %
            (self.systemtap_dir, dejagnu_dir))

        # After we are done with this iteration, we move the log files to
        # the results dir
        sum = os.path.join(testsuite, 'systemtap.sum')
        log = os.path.join(testsuite, 'systemtap.log')

        if self.iteration:
            logfile = 'systemtap.log.%d' % self.iteration
            sumfile = 'systemtap.sum.%d' % self.iteration
        else:
            logfile = 'systemtap.log.profile'
            sumfile = 'systemtap.sum.profile'

        self.logfile = os.path.join(self.resultsdir, logfile)
        self.sumfile = os.path.join(self.resultsdir, sumfile)

        shutil.move(log, self.logfile)
        shutil.move(sum, self.sumfile)


    def postprocess_iteration(self):
        os.chdir(self.resultsdir)

        r = re.compile("# of (.*)\t(\d+)")

        f = open(self.sumfile, 'r')
        keyval = {}
        for line in f:
            result = r.match(line)
            if result:
                key = result.group(1)
                key = key.strip().replace(' ', '_')
                value = result.group(2)
                keyval[key] = value
        f.close()

        self.write_perf_keyval(keyval)
