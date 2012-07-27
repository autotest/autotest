import os, re, glob, logging
from autotest.client.shared import error, software_manager
from autotest.client import test, utils, os_dep

class xfstests(test.test):

    version = 2

    PASSED_RE = re.compile(r'Passed all \d+ tests')
    FAILED_RE = re.compile(r'Failed \d+ of \d+ tests')
    NA_RE = re.compile(r'Passed all 0 tests')
    NA_DETAIL_RE = re.compile(r'(\d{3})\s*(\[not run\])\s*(.*)')

    SW_DEPS = {'Fedora' : ['autoconf', 'libtool', 'gcc', 'xfsprogs', 'xfsdump',
                           'xfsprogs-devel', 'xfsprogs-qa-devel',
                           'libuuid-devel', 'libacl-devel',
                           'libattr-devel']}

    def _get_available_tests(self):
        tests = glob.glob('???.out')
        tests += glob.glob('???.out.linux')
        tests = [t.replace('.linux', '') for t in tests]
        tests_list = [t[:-4] for t in tests if os.path.exists(t[:-4])]
        tests_list.sort()
        return tests_list


    def _run_sub_test(self, test):
        os.chdir(self.srcdir)
        output = utils.system_output('./check %s' % test,
                                     ignore_status=True,
                                     retain_output=True)
        lines = output.split('\n')
        result_line = lines[-1]

        if self.NA_RE.match(result_line):
            detail_line = lines[-3]
            match = self.NA_DETAIL_RE.match(detail_line)
            if match is not None:
                error_msg = match.groups()[2]
            else:
                error_msg = 'Test dependency failed, test not run'
            raise error.TestNAError(error_msg)

        elif self.FAILED_RE.match(result_line):
            raise error.TestError('Test error, check debug logs for complete '
                                  'test output')

        elif self.PASSED_RE.match(result_line):
            return

        else:
            raise error.TestError('Could not assert test success or failure, '
                                  'assuming failure. Please check debug logs')


    def _distro_has_deps_annotated(self):
        '''
        Checks if the current distro has a list of package dependencies
        '''
        distro = utils.get_os_vendor()
        return self.SW_DEPS.has_key(distro)


    def _install_software_deps(self):
        '''
        Install the software dependecies for the detected distro
        '''
        distro = utils.get_os_vendor()
        deps = self.SW_DEPS.get(distro, None)
        if deps is not None:
            s = software_manager.SoftwareManager()
            for d in deps:
                if not s.check_installed(d):
                    logging.info('Installing xfstests dependency "%s"', d)
                    s.install(d)


    def setup(self, tarball='xfstests.tar.bz2', use_package_manager=True):
        '''
        Sets up the environment necessary for running xfstests
        '''
        if use_package_manager and self._distro_has_deps_annotated():
            self._install_software_deps()

        #
        # Anticipate failures due to missing devel tools, libraries, headers
        # and xfs commands
        #
        os_dep.command('autoconf')
        os_dep.command('autoheader')
        os_dep.command('libtool')
        os_dep.library('libuuid.so.1')
        os_dep.header('xfs/xfs.h')
        os_dep.header('attr/xattr.h')
        os_dep.header('sys/acl.h')
        os_dep.command('mkfs.xfs')
        os_dep.command('xfs_db')
        os_dep.command('xfs_bmap')
        os_dep.command('xfsdump')
        self.job.require_gcc()

        tarball = utils.unmap_url(self.bindir, tarball, self.tmpdir)
        utils.extract_tarball_to_dir(tarball, self.srcdir)
        os.chdir(self.srcdir)
        utils.make()

        logging.debug("Available tests in srcdir: %s" %
                      ", ".join(self._get_available_tests()))


    def run_once(self, test_number):
        os.chdir(self.srcdir)
        if test_number == '000':
            logging.debug('Dummy test to setup xfstests')
            return

        if test_number not in self._get_available_tests():
            raise error.TestError('test file %s not found' % test_number)

        logging.debug("Running test: %s" % test_number)
        self._run_sub_test(test_number)
