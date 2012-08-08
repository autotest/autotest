import logging, os
from autotest.client import test, utils
from autotest.client.shared import git, error

class autotest_regression(test.test):
    version = 1
    @error.context_aware
    def run_once(self, uri='git://github.com/autotest/autotest.git',
                 branch='next', commit=None, base_uri=None):
        n_fail = []
        error.context("Checking out autotest", logging.info)
        a_repo = git.GitRepoHelper(uri, branch, commit,
                                   destination_dir=self.srcdir,
                                   base_uri=base_uri)
        a_repo.execute()
        top_commit = a_repo.get_top_commit()
        encoded_version = "%s:%s:%s" % (uri, branch, top_commit)
        self.write_test_keyval({"software_version_autotest": encoded_version})

        error.context("Running unittest suite", logging.info)
        unittest_path = os.path.join(self.srcdir, 'utils', 'unittest_suite.py')
        try:
            utils.system(unittest_path)
        except error.CmdError, e:
            n_fail.append('Unittest failed: %s' % e.result_obj.stderr)

        error.context("Running full tree check", logging.info)
        check_path = os.path.join(self.srcdir, 'utils', 'check_patch.py')
        try:
            utils.system("%s --full --yes" % check_path)
        except error.CmdError, e:
            n_fail.append('Full tree check shows errors: %s' %
                          e.result_obj.stderr)

        error.context("Running a sleeptest", logging.info)
        alocal_path = os.path.join(self.srcdir, 'client', 'autotest-local')
        try:
            utils.system("%s run sleeptest" % alocal_path)
        except error.CmdError, e:
            n_fail.append('Sleeptest failed: %s' %
                          e.result_obj.stderr)

        if n_fail:
            raise error.TestFail("Autotest regression failed: %s" %
                                 " ".join(n_fail))