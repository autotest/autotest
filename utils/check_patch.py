#!/usr/bin/python
"""
Script to verify errors on autotest code contributions (patches).
The workflow is as follows:

 * Patch will be applied and eventual problems will be notified.
 * If there are new files created, remember user to add them to VCS.
 * If any added file looks like a executable file, remember user to make them
   executable.
 * If any of the files added or modified introduces trailing whitespaces, tabs
   or incorrect indentation, report problems.
 * If any of the files have problems during pylint validation, report failures.
 * If any of the files changed have a unittest suite, run the unittest suite
   and report any failures.

Usage: check_patch.py -p [/path/to/patch]
       check_patch.py -i [patchwork id]
       check_patch.py -g [github pull request id]
       check_patch.py --full --yes [check the entire tree]

:copyright: Red Hat Inc, 2009.
:author: Lucas Meneghel Rodrigues <lmr@redhat.com>
"""

import os
import stat
import logging
import sys
import optparse
import re
import urllib
import shutil
import unittest
import tempfile
try:
    import autotest.common as common
except ImportError:
    import common

from autotest.client.shared import utils, error, logging_config
from autotest.client.shared import logging_manager
import run_pylint
import reindent
import run_pep8

UTILS_DIRNAME = os.path.dirname(sys.modules[__name__].__file__)
TOP_LEVEL_DIRNAME = os.path.abspath(os.path.dirname(UTILS_DIRNAME))
CODESPELL_PATH = os.path.join(UTILS_DIRNAME, 'codespell', 'codespell.py')

# Hostname of patchwork server to use
PWHOST = "patchwork.virt.bos.redhat.com"

TMP_FILE_DIR = tempfile.gettempdir()
LOG_FILE_PATH = os.path.join(TMP_FILE_DIR, 'check-patch.log')


# Rely on built-in recursion limit to limit number of directories searched
def license_project_name(path):
    '''
    Locate the nearest LICENSE file, take first word as the project name
    '''
    if path == '/' or path == '.':
        raise RuntimeError('Ran out of directories searching for LICENSE file')
    try:
        license_file = file(os.path.join(path, 'LICENSE'), 'r')
        first_word = license_file.readline().strip().split()[0].lower()
        return first_word
    except IOError:
        # Recurse search parent of path's directory
        return license_project_name(os.path.dirname(path))

PROJECT_NAME = license_project_name(os.path.dirname(os.path.abspath(__file__)))


EXTENSION_BLACKLIST = {
    'autotest': ["common.py", ".java", ".html", ".png", ".css",
                 ".xml", ".pyc", ".orig", ".rej", ".bak", ".so"],
    'virt-test': ["common.py", ".svn", ".git", ".pyc", ".orig",
                  ".rej", ".bak", ".so", ".cfg", ".ks", ".preseed",
                  ".steps", ".c", ".xml", ".sif", ".cs", ".ini",
                  ".exe", "logs", "shared/data"]
}


DIR_BLACKLIST = {
    'autotest': [".svn", ".git", "logs", "virt", "site-packages",
                 "ExternalSource"],
    'virt-test': [".svn", ".git", "data", "logs"]
}


FILE_BLACKLIST = {
    'autotest': ['client/tests/virt/qemu/tests/stepmaker.py',
                 'utils/run_pylint.py', 'Makefile', '.travis.yml'],
}


PY24_BLACKLIST = {
    'virt-test': ['qemu/tests/stepmaker.py', 'virttest/step_editor.py',
                  'shared/scripts/cb.py']
}


INDENT_BLACKLIST = {
    'autotest': ['cli/job_unittest.py', 'Makefile', '.travis.yml']
}


class CheckPatchLoggingConfig(logging_config.LoggingConfig):

    def configure_logging(self, results_dir=None, verbose=True):
        super(CheckPatchLoggingConfig, self).configure_logging(
            use_console=True,
            verbose=verbose)
        self.add_file_handler(file_path=LOG_FILE_PATH)


class VCS(object):

    """
    Abstraction layer to the version control system.
    """

    def __init__(self):
        """
        Class constructor. Guesses the version control name and instantiates it
        as a backend.
        """
        backend_name = self.guess_vcs_name()
        if backend_name == "SVN":
            self.backend = SubVersionBackend()
            self.type = "subversion"
        elif backend_name == "git":
            self.backend = GitBackend()
            self.type = "git"
        else:
            self.backend = None

    def guess_vcs_name(self):
        if os.path.isdir(".svn"):
            return "SVN"
        elif os.path.exists(".git"):
            return "git"
        else:
            logging.error("Could not figure version control system. Are you "
                          "on a working directory? Aborting.")
            sys.exit(1)

    def get_unknown_files(self):
        """
        Return a list of files unknown to the VCS.
        """
        return self.backend.get_unknown_files()

    def get_modified_files(self):
        """
        Return a list of files that were modified, according to the VCS.
        """
        return self.backend.get_modified_files()

    def is_file_tracked(self, fl):
        """
        Return whether a file is tracked by the VCS.
        """
        return self.backend.is_file_tracked(fl)

    def add_untracked_file(self, fl):
        """
        Add an untracked file to version control.
        """
        return self.backend.add_untracked_file(fl)

    def revert_file(self, fl):
        """
        Restore file according to the latest state on the reference repo.
        """
        return self.backend.revert_file(fl)

    def apply_patch(self, patch):
        """
        Applies a patch using the most appropriate method to the particular VCS.
        """
        return self.backend.apply_patch(patch)

    def update(self):
        """
        Updates the tree according to the latest state of the public tree
        """
        return self.backend.update()


class SubVersionBackend(object):

    """
    Implementation of a subversion backend for use with the VCS abstraction
    layer.
    """

    def __init__(self):
        self.ignored_extension_list = ['.orig', '.bak']

    def get_unknown_files(self):
        status = utils.system_output("svn status --ignore-externals")
        unknown_files = []
        for line in status.split("\n"):
            status_flag = line[0]
            if line and status_flag == "?":
                for extension in self.ignored_extension_list:
                    if not line.endswith(extension):
                        unknown_files.append(line[1:].strip())
        return unknown_files

    def get_modified_files(self):
        status = utils.system_output("svn status --ignore-externals")
        modified_files = []
        for line in status.split("\n"):
            status_flag = line[0]
            if line and status_flag == "M" or status_flag == "A":
                modified_files.append(line[1:].strip())
        return modified_files

    def is_file_tracked(self, fl):
        stdout = None
        try:
            cmdresult = utils.run("svn status --ignore-externals %s" % fl,
                                  verbose=False)
            stdout = cmdresult.stdout
        except error.CmdError:
            return False

        if stdout is not None:
            if stdout:
                if stdout.startswith("?"):
                    return False
                else:
                    return True
            else:
                return True
        else:
            return False

    def add_untracked_file(self, fl):
        """
        Add an untracked file under revision control.

        :param file: Path to untracked file.
        """
        try:
            utils.run('svn add %s' % fl)
        except error.CmdError, e:
            logging.error("Problem adding file %s to svn: %s", fl, e)
            sys.exit(1)

    def revert_file(self, fl):
        """
        Revert file against last revision.

        :param file: Path to file to be reverted.
        """
        try:
            utils.run('svn revert %s' % fl)
        except error.CmdError, e:
            logging.error("Problem reverting file %s: %s", fl, e)
            sys.exit(1)

    def apply_patch(self, patch):
        """
        Apply a patch to the code base. Patches are expected to be made using
        level -p1, and taken according to the code base top level.

        :param patch: Path to the patch file.
        """
        try:
            utils.system_output("patch -p1 < %s" % patch)
        except:
            logging.error("Patch applied incorrectly. Possible causes: ")
            logging.error("1 - Patch might not be -p1")
            logging.error("2 - You are not at the top of the autotest tree")
            logging.error("3 - Patch was made using an older tree")
            logging.error("4 - Mailer might have messed the patch")
            sys.exit(1)

    def update(self):
        try:
            utils.system("svn update")
        except error.CmdError, e:
            logging.error("SVN tree update failed: %s" % e)


class GitBackend(object):

    """
    Implementation of a git backend for use with the VCS abstraction layer.
    """

    def __init__(self):
        self.ignored_extension_list = ['.orig', '.bak']

    def get_unknown_files(self):
        status = utils.system_output("git status --porcelain")
        unknown_files = []
        for line in status.split("\n"):
            if line:
                status_flag = line.split()[0]
                if status_flag == "??":
                    for extension in self.ignored_extension_list:
                        if not line.endswith(extension):
                            unknown_files.append(line[2:].strip())
        return unknown_files

    def get_modified_files(self):
        status = utils.system_output("git status --porcelain")
        modified_files = []
        for line in status.split("\n"):
            if line:
                status_flag = line.split()[0]
                if status_flag in ["M", "A"]:
                    modified_files.append(line.split()[-1])
        return modified_files

    def is_file_tracked(self, fl):
        try:
            utils.run("git ls-files %s --error-unmatch" % fl,
                      verbose=False)
            return True
        except error.CmdError:
            return False

    def add_untracked_file(self, fl):
        """
        Add an untracked file under revision control.

        :param file: Path to untracked file.
        """
        try:
            utils.run('git add %s' % fl)
        except error.CmdError, e:
            logging.error("Problem adding file %s to git: %s", fl, e)
            sys.exit(1)

    def revert_file(self, fl):
        """
        Revert file against last revision.

        :param file: Path to file to be reverted.
        """
        try:
            utils.run('git checkout %s' % fl)
        except error.CmdError, e:
            logging.error("Problem reverting file %s: %s", fl, e)
            sys.exit(1)

    def apply_patch(self, patch):
        """
        Apply a patch to the code base using git am.

        A new branch will be created with the patch name.

        :param patch: Path to the patch file.
        """
        utils.run("git checkout master")
        utils.run("git checkout -b %s" %
                  os.path.basename(patch).rstrip(".patch"))
        try:
            utils.run("git am -3 %s" % patch, verbose=False)
        except error.CmdError, e:
            logging.error("Failed to apply patch to the git repo: %s" % e)
            sys.exit(1)

    def update(self):
        return
        try:
            utils.system("git pull")
        except error.CmdError, e:
            logging.error("git tree update failed: %s" % e)


def run_codespell(path):
    cmd = CODESPELL_PATH + " -w " + path
    utils.system(CODESPELL_PATH, ignore_status=True)


class FileChecker(object):

    """
    Picks up a given file and performs various checks, looking after problems
    and eventually suggesting solutions.
    """

    def __init__(self, path=None, vcs=None, confirm=False):
        """
        Class constructor, sets the path attribute.

        :param path: Path to the file that will be checked.
        :param vcs: Version control system being used.
        :param confirm: Whether to answer yes to all questions asked without
                prompting the user.
        """
        if path is not None:
            self.set_path(path=path, vcs=vcs, confirm=confirm)

    def set_path(self, path, vcs=None, confirm=False):
        self.path = path
        self.vcs = vcs
        self.confirm = confirm
        self.basename = os.path.basename(self.path)

        if self.basename.endswith('.py'):
            self.is_python = True
        else:
            self.is_python = False

        mode = os.stat(self.path)[stat.ST_MODE]
        self.is_executable = mode & stat.S_IXUSR

        checked_file = open(self.path, "r")
        self.first_line = checked_file.readline()
        checked_file.close()
        if "python" in self.first_line:
            self.is_python = True

        self.indent_exceptions = INDENT_BLACKLIST.get(PROJECT_NAME, [])
        self.check_exceptions = FILE_BLACKLIST.get(PROJECT_NAME, [])

        version = sys.version_info[0:2]
        if version < (2, 5):
            self.check_exceptions += PY24_BLACKLIST.get(PROJECT_NAME, [])

        if self.is_python:
            logging.debug("Checking file %s", self.path)
        if self.is_python and not self.path.endswith(".py"):
            self.bkp_path = "%s-cp.py" % self.path
            shutil.copyfile(self.path, self.bkp_path)
        else:
            self.bkp_path = None

    def _get_checked_filename(self):
        if self.bkp_path is not None:
            return self.bkp_path
        else:
            return self.path

    def _check_indent(self):
        """
        Verifies the file with the reindent module

        This tool performs the following checks on python files:

          * Trailing whitespaces
          * Tabs
          * End of line
          * Incorrect indentation

        And will automatically correct problems.
        """
        success = True
        for exc in self.indent_exceptions:
            if re.search(exc, self.path):
                return success

        path = self._get_checked_filename()
        try:
            f = open(path)
        except IOError, msg:
            logging.error("Error opening %s: %s", path, str(msg))
            return False

        r = reindent.Reindenter(f)
        f.close()
        try:
            if r.run():
                success = False
                logging.info("Reindenting %s", path)
                f = open(path, "w")
                r.write(f)
                f.close()
        except:
            pass

        if not success and path != self.path:
            shutil.copyfile(path, self.path)

        return success

    def _check_code(self):
        """
        Verifies the file with run_pylint.

        This tool will call the static code checker pylint using the special
        autotest conventions and warn about problems. Some of the problems
        reported might be false positive, but it's allways good to look at
        them.
        """
        success = True
        for exc in self.check_exceptions:
            if re.search(exc, self.path):
                return success

        path = self._get_checked_filename()

        try:
            if run_pylint.check_file(path):
                success = False
        except Exception, details:
            logging.error("Pylint exception while verifying %s, details: %s",
                          path, details)
            success = False

        return success

    def _check_pep8(self):
        """
        Verifies the file with run_pep8.
        """
        success = True
        for exc in self.check_exceptions:
            if re.search(exc, self.path):
                return success

        path = self._get_checked_filename()

        try:
            if run_pep8.check(path):
                success = False
                logging.error("File non PEP8 compliant: %s", path[2:])
        except Exception, details:
            logging.error(
                "PEP8 linter exception while verifying %s, details: %s",
                path, details)
            success = False

        return success

    def _check_codespell(self):
        """
        Verifies the file with codespell.
        """
        success = True
        for exc in self.check_exceptions:
            if re.search(exc, self.path):
                return success

        path = self._get_checked_filename()

        run_codespell(path)

        return success

    def _check_unittest(self):
        """
        Verifies if the file in question has a unittest suite, if so, run the
        unittest and report on any failures. This is important to keep our
        unit tests up to date.
        """
        success = True
        if "unittest" not in self.basename:
            stripped_name = self.basename.rstrip(".py")
            unittest_name = stripped_name + "_unittest.py"
            unittest_path = self.path.replace(self.basename, unittest_name)
            if os.path.isfile(unittest_path):
                mod_names = unittest_path.rstrip(".py")
                mod_names = mod_names.split("/")
                try:
                    from_module = __import__(mod_names[0], globals(), locals(),
                                             [mod_names[-1]])
                    mod = getattr(from_module, mod_names[-1])
                    test = unittest.defaultTestLoader.loadTestsFromModule(mod)
                    suite = unittest.TestSuite(test)
                    runner = unittest.TextTestRunner()
                    result = runner.run(suite)
                    if result.errors or result.failures:
                        success = False
                        msg = ('%s had %d failures and %d errors.' %
                               ('.'.join(mod_names), len(result.failures),
                                len(result.errors)))
                        logging.error(msg)
                except ImportError:
                    logging.error("Unable to run unittest %s" %
                                  ".".join(mod_names))

        return success

    def _check_permissions(self):
        """
        Verifies the execution permissions.

          * Files with no shebang and execution permissions are reported.
          * Files with shebang and no execution permissions are reported.
        """
        if self.first_line.startswith("#!"):
            if not self.is_executable:
                if self.vcs.type == "subversion":
                    utils.run("svn propset svn:executable ON %s" % self.path,
                              ignore_status=True)
                elif self.vcs.type == "git":
                    utils.run("chmod +x %s" % self.path,
                              ignore_status=True)
        else:
            if self.is_executable:
                if self.vcs.type == "subversion":
                    utils.run("svn propdel svn:executable %s" % self.path,
                              ignore_status=True)
                elif self.vcs.type == "git":
                    utils.run("chmod -x %s" % self.path,
                              ignore_status=True)

    def report(self, skip_unittest=False):
        """
        Executes all required checks, if problems are found, the possible
        corrective actions are listed.
        """
        success = True
        self._check_permissions()
        if self.is_python:
            if not self._check_indent():
                success = False
            if not self._check_code():
                success = False
            if not self._check_pep8():
                success = False
            if not self._check_codespell():
                success = False
            if not skip_unittest:
                if not self._check_unittest():
                    success = False

        if self.bkp_path is not None and os.path.isfile(self.bkp_path):
            os.unlink(self.bkp_path)

        return success


class PatchChecker(object):

    def __init__(self, patch=None, patchwork_id=None, github_id=None,
                 pwhost=None, vcs=None, confirm=False):
        self.confirm = confirm
        self.files_failed_check = []
        self.base_dir = TMP_FILE_DIR
        if pwhost is None:
            self.pwhost = PWHOST
        else:
            self.pwhost = pwhost

        if patch:
            self.patch = os.path.abspath(patch)

        if patchwork_id:
            self.patch = self._fetch_from_patchwork(patchwork_id)

        if github_id:
            self.patch = self._fetch_from_github(github_id)

        if not os.path.isfile(self.patch):
            logging.error("Invalid patch file %s provided. Aborting.",
                          self.patch)
            sys.exit(1)

        self.vcs = vcs
        changed_files_before = self.vcs.get_modified_files()
        if changed_files_before:
            logging.error("Repository has changed files prior to patch "
                          "application. ")
            answer = utils.ask("Would you like to revert them?",
                               auto=self.confirm)
            if answer == "n":
                logging.error("Not safe to proceed without reverting files.")
                sys.exit(1)
            else:
                for changed_file in changed_files_before:
                    self.vcs.revert_file(changed_file)

        self.untracked_files_before = self.vcs.get_unknown_files()
        self.vcs.update()

    def _fetch_from_patchwork(self, pw_id):
        """
        Gets a patch file from patchwork and puts it under the cwd so it can
        be applied.

        :param id: Patchwork patch id. It can be a string with comma separated
                github ids.
        """
        collection = os.path.join(self.base_dir, 'patchwork-%s.patch' %
                                  utils.generate_random_string(4))
        collection_rw = open(collection, 'w')

        for i in pw_id.split(","):
            patch_url = "http://%s/patch/%s/mbox/" % (self.pwhost, i)
            patch_dest = os.path.join(self.base_dir, 'patchwork-%s.patch' % i)
            patch = utils.get_file(patch_url, patch_dest)
            # Patchwork sometimes puts garbage on the path, such as long
            # sequences of underscores (_______). Get rid of those.
            patch_ro = open(patch, 'r')
            patch_contents = patch_ro.readlines()
            patch_ro.close()
            for line in patch_contents:
                if not line.startswith("___"):
                    collection_rw.write(line)
        collection_rw.close()

        return collection

    def _fetch_from_github(self, gh_id):
        """
        Gets a patch file from patchwork and puts it under the cwd so it can
        be applied.

        :param gh_id: Patchwork patch id.
        """
        url_template = "https://github.com/autotest/%s" % PROJECT_NAME
        url_template += "/pull/%s.patch"
        patch_url = url_template % gh_id
        patch_dest = os.path.join(self.base_dir, 'github-%s.patch' % gh_id)
        urllib.urlretrieve(patch_url, patch_dest)
        return patch_dest

    def _check_files_modified_patch(self):
        modified_files_after = []
        if self.vcs.type == "subversion":
            untracked_files_after = self.vcs.get_unknown_files()
            modified_files_after = self.vcs.get_modified_files()
            add_to_vcs = []
            for untracked_file in untracked_files_after:
                if untracked_file not in self.untracked_files_before:
                    add_to_vcs.append(untracked_file)

            if add_to_vcs:
                logging.info("The files: ")
                for untracked_file in add_to_vcs:
                    logging.info(untracked_file)
                logging.info("Might need to be added to VCS")
                answer = utils.ask("Would you like to add them to VCS ?")
                if answer == "y":
                    for untracked_file in add_to_vcs:
                        self.vcs.add_untracked_file(untracked_file)
                        modified_files_after.append(untracked_file)
                elif answer == "n":
                    pass
        elif self.vcs.type == "git":
            patch = open(self.patch)
            for line in patch.readlines():
                if line.startswith("diff --git"):
                    m_file = line.split()[-1][2:]
                    if m_file not in modified_files_after:
                        modified_files_after.append(m_file)
            patch.close()

        for modified_file in modified_files_after:
            # Additional safety check, new commits might introduce
            # new directories
            if os.path.isfile(modified_file):
                file_checker = FileChecker(path=modified_file, vcs=self.vcs,
                                           confirm=self.confirm)
                if not file_checker.report():
                    self.files_failed_check.append(modified_file)
        if self.files_failed_check:
            return False
        else:
            return True

    def check(self):
        self.vcs.apply_patch(self.patch)
        return self._check_files_modified_patch()


if __name__ == "__main__":
    parser = optparse.OptionParser()
    parser.add_option('-l', '--patch', dest="local_patch", action='store',
                      help='path to a patch file that will be checked')
    parser.add_option('-p', '--patchwork-id', dest="pw_id", action='store',
                      help='id of a given patchwork patch')
    parser.add_option('-g', '--github-id', dest="gh_id", action='store',
                      help='id of a given github patch')
    parser.add_option('--verbose', dest="debug", action='store_true',
                      help='include debug messages in console output')
    parser.add_option('-f', '--full-check', dest="full_check",
                      action='store_true',
                      help='check the full tree for corrective actions')
    parser.add_option('--patchwork-host', dest="patchwork_host",
                      help='patchwork custom server url')
    parser.add_option('-y', '--yes', dest="confirm",
                      action='store_true',
                      help='Answer yes to all questions')

    options, args = parser.parse_args()
    local_patch = options.local_patch
    pw_id = options.pw_id
    gh_id = options.gh_id
    debug = options.debug
    run_pylint.set_verbosity(debug)
    full_check = options.full_check
    confirm = options.confirm
    pwhost = options.patchwork_host
    vcs = VCS()
    if vcs.backend is None:
        vcs = None

    logging_manager.configure_logging(CheckPatchLoggingConfig(), verbose=debug)
    logging.info("Detected project name: %s", PROJECT_NAME)
    logging.info("Log saved to file: %s", LOG_FILE_PATH)
    extension_blacklist = EXTENSION_BLACKLIST.get(PROJECT_NAME, [])
    dir_blacklist = DIR_BLACKLIST.get(PROJECT_NAME, [])

    if full_check:
        failed_paths = []
        run_pylint.set_verbosity(False)
        logging.info("%s spell check", PROJECT_NAME)
        logging.info("")
        run_codespell(TOP_LEVEL_DIRNAME)

        logging.info("%s full tree check", PROJECT_NAME)
        logging.info("")

        if PROJECT_NAME == 'autotest' and os.path.isfile("tko/Makefile"):
            proto_cmd = "make -C tko"
            try:
                utils.system(proto_cmd)
            except error.CmdError:
                doc = "https://github.com/autotest/autotest/wiki/UnittestSuite"
                logging.error("Command %s failed. Please check if you have "
                              "the google protocol buffer compiler, refer to "
                              "%s for more info", proto_cmd, doc)
                sys.exit(1)

        file_checker = FileChecker()
        for root, dirs, files in os.walk("."):
            dirs[:] = [d for d in dirs if d not in dir_blacklist]

            t_files = []
            for f in files:
                add = True
                for extension in extension_blacklist:
                    if f.endswith(extension):
                        add = False
                if add:
                    t_files.append(f)
            files = t_files

            for f in files:
                check = True
                path = os.path.join(root, f)
                if check:
                    if vcs is not None:
                        if not vcs.is_file_tracked(fl=path):
                            check = False
                if check:
                    file_checker.set_path(path=path, vcs=vcs, confirm=confirm)
                    if not file_checker.report(skip_unittest=True):
                        failed_paths.append(path)

        if failed_paths:
            logging.error("Full tree check found files with problems:")
            for fp in failed_paths:
                logging.error(fp)
            logging.error("Please verify the problems and address them")
            sys.exit(1)
        else:
            logging.info("All passed!")
            sys.exit(0)

    else:
        if local_patch:
            logging.info("Checking local patch %s", local_patch)
            logging.info("")
            patch_checker = PatchChecker(patch=local_patch, vcs=vcs,
                                         confirm=confirm)
        elif pw_id:
            logging.info("Checking patchwork patch IDs %s", pw_id)
            logging.info("")
            patch_checker = PatchChecker(patchwork_id=pw_id, pwhost=pwhost,
                                         vcs=vcs,
                                         confirm=confirm)
        elif gh_id:
            logging.info("Checking github pull request #%s", gh_id)
            logging.info("")
            patch_checker = PatchChecker(github_id=gh_id, vcs=vcs,
                                         confirm=confirm)
        else:
            logging.error('No patch or patchwork id specified. Aborting.')
            sys.exit(1)

        if patch_checker.check():
            sys.exit(0)
        else:
            logging.error("Patch checking found files with problems:")
            for fp in patch_checker.files_failed_check:
                logging.error(fp)
            logging.error("Please verify the problems and address them")
            sys.exit(1)
