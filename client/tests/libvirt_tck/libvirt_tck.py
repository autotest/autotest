import os, re, shutil, logging

from autotest_lib.client.common_lib import error
from autotest_lib.client.bin import utils, test


class libvirt_tck(test.test):
    """
    Autotest wrapper for the libvirt Technology Compatibility toolkit.

    The libvirt TCK provides a framework for performing testing
    of the integration between libvirt drivers, the underlying virt
    hypervisor technology, related operating system services and system
    configuration. The idea (and name) is motivated by the Java TCK.

    @see: git clone git://libvirt.org/libvirt-tck.git
    @author: Daniel Berrange <berrange@redhat.com>
    """
    version = 1
    TESTDIR = '/usr/share/libvirt-tck/tests'

    def setup(self, tarball='Sys-Virt-TCK-v0.1.0.tar.gz'):
        # Install cpanminus script
        try:
            utils.system('(curl -L http://cpanmin.us | perl - App::cpanminus)2>&1')
        except error.CmdError, e:
            raise error.TestError("Failed to install cpanminus script.")

        tarpath = utils.unmap_url(self.bindir, tarball)
        utils.extract_tarball_to_dir(tarpath, self.srcdir)
        os.chdir(self.srcdir)

        output = utils.system_output('perl Makefile.PL 2>&1', retain_output=True)

        required_mods = list(set(re.findall("[^ ']*::[^ ']*", output)))

        # Resolve perl modules dependencies
        if required_mods:
            for mod in required_mods:
                ret = utils.system('cpanm %s 2>&1' % mod)
                if ret != 0:
                    raise error.TestError("Failed to install module %s" % mod)

        utils.system('make')
        utils.system('make test')
        utils.system('make install')


    def get_testcases(self, testcasecfg, item):
        flag = 0
        testcases = []
        fh = open(testcasecfg, "r")
        for eachLine in fh:
            line = eachLine.strip()

            if line.startswith('#'):
                continue

            if flag == 0 and not line:
                continue

            if item == line[:-1]:
                flag = 1
                continue

            if flag == 1 and not line:
                flag = 0
                break

            if flag == 1 and line[0].isdigit():
                testcases.append(line)
                continue

        fh.close()
        return testcases


    def run_once(self, item=None):
        failed_tests = []
        if item is None:
            raise error.TestError("No item provided")

        default_cfg = os.path.join(self.bindir, 'default.cfg')
        ks_cfg = os.path.join(self.bindir, 'ks.cfg')

        testcase_cfg = os.path.join(self.bindir, 'testcase.cfg')
        item_path = os.path.join(self.TESTDIR, item)
        testcases = self.get_testcases(testcase_cfg, item)

        shutil.copyfile(ks_cfg, '/etc/libvirt-tck/ks.cfg')

        logging.debug("Available testcases for item %s: %s", item, testcases)

        for testcase in testcases:
            testcase_path = os.path.join(item_path, testcase)
            testcase_basename = testcase.rstrip(".t")
            output = os.path.join(self.resultsdir, '%s.tap' % testcase_basename)
            t_output = open(output, 'w')
            os.environ['LIBVIRT_TCK_CONFIG'] = default_cfg
            t_cmd = ('perl %s' % testcase_path)
            try:
                try:
                    cmd_result = utils.run(t_cmd, stdout_tee=t_output,
                                           stderr_tee=t_output)
                finally:
                    t_output.close()
            except error.CmdError:
                failed_tests.append(testcase)

        if failed_tests:
            raise error.TestFail('FAIL: %s' % failed_tests)
