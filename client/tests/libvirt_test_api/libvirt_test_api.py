import os, re, shutil, glob, logging

from autotest_lib.client.common_lib import error
from autotest_lib.client.bin import utils, test, os_dep


class libvirt_test_api(test.test):
    version = 1
    def setup(self, tarball='libvirt-test-API.tar.gz'):
        tarpath = utils.unmap_url(self.bindir, tarball)
        utils.extract_tarball_to_dir(tarpath, self.srcdir)


    def initialize(self):
        try:
            import pexpect
        except ImportError:
            raise error.TestError("Missing python library pexpect. You have to "
                                  "install the package python-pexpect or the "
                                  "equivalent for your distro")
        try:
            os_dep.command("nmap")
        except ValueError:
            raise error.TestError("Missing required command nmap. You have to"
                                  "install the package nmap or the equivalent"
                                  "for your distro")


    def get_tests_from_cfg(self, cfg, item):
        """
        Get all available tests for the given item in the config file cfg.

        @param cfg: Path to config file.
        @param item: Item that we're going to find tests for.
        """
        flag = 0
        testcases = []
        cfg = open(cfg, "r")
        for line in cfg.readlines():
            line = line.strip()

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

            if flag == 1 and line.endswith('.conf'):
                testcases.append(line)
                continue

        cfg.close()
        return testcases


    def run_once(self, item=''):
        if not item:
            raise error.TestError('No test item provided')

        logging.info('Testing item %s', item)

        cfg_files = glob.glob(os.path.join(self.bindir, '*.cfg'))
        for src in cfg_files:
            basename = os.path.basename(src)
            dst = os.path.join(self.srcdir, basename)
            shutil.copyfile(src, dst)

        config_files_cfg = os.path.join(self.bindir, 'config_files.cfg')
        test_items = self.get_tests_from_cfg(config_files_cfg, item)
        if not test_items:
            raise error.TestError('No test avaliable for item %s in '
                                 'config_files.cfg' % item)

        os.chdir(self.srcdir)
        failed_tests = []
        for test_item in test_items:
            try:
                cfg_test = os.path.join('cases', test_item)
                utils.system('python libvirt-test-api.py -c %s' % cfg_test)
            except error.CmdError:
                logs = glob.glob(os.path.join('log', '*'))
                for log in logs:
                    shutil.rmtree(log)
                failed_tests.append(os.path.basename(test_item).split('.')[0])

        if failed_tests:
            raise error.TestFail('Tests failed for item %s: %s' %
                                 (item, failed_tests))
