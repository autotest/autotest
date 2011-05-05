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

@copyright: Red Hat Inc, 2009.
@author: Lucas Meneghel Rodrigues <lmr@redhat.com>
"""

import os, stat, logging, sys, optparse, time
import common
from autotest_lib.client.common_lib import utils, error, logging_config
from autotest_lib.client.common_lib import logging_manager


class CheckPatchLoggingConfig(logging_config.LoggingConfig):
    def configure_logging(self, results_dir=None, verbose=False):
        super(CheckPatchLoggingConfig, self).configure_logging(use_console=True,
                                                               verbose=verbose)


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


    def guess_vcs_name(self):
        if os.path.isdir(".svn"):
            return "SVN"
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


    def add_untracked_file(self, file):
        """
        Add an untracked file to version control.
        """
        return self.backend.add_untracked_file(file)


    def revert_file(self, file):
        """
        Restore file according to the latest state on the reference repo.
        """
        return self.backend.revert_file(file)


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
        logging.debug("Subversion VCS backend initialized.")
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


    def add_untracked_file(self, file):
        """
        Add an untracked file under revision control.

        @param file: Path to untracked file.
        """
        try:
            utils.run('svn add %s' % file)
        except error.CmdError, e:
            logging.error("Problem adding file %s to svn: %s", file, e)
            sys.exit(1)


    def revert_file(self, file):
        """
        Revert file against last revision.

        @param file: Path to file to be reverted.
        """
        try:
            utils.run('svn revert %s' % file)
        except error.CmdError, e:
            logging.error("Problem reverting file %s: %s", file, e)
            sys.exit(1)


    def apply_patch(self, patch):
        """
        Apply a patch to the code base. Patches are expected to be made using
        level -p1, and taken according to the code base top level.

        @param patch: Path to the patch file.
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
            utils.system("svn update", ignore_status=True)
        except error.CmdError, e:
            logging.error("SVN tree update failed: %s" % e)


class FileChecker(object):
    """
    Picks up a given file and performs various checks, looking after problems
    and eventually suggesting solutions.
    """
    def __init__(self, path, confirm=False):
        """
        Class constructor, sets the path attribute.

        @param path: Path to the file that will be checked.
        @param confirm: Whether to answer yes to all questions asked without
                prompting the user.
        """
        self.path = path
        self.confirm = confirm
        self.basename = os.path.basename(self.path)
        if self.basename.endswith('.py'):
            self.is_python = True
        else:
            self.is_python = False

        mode = os.stat(self.path)[stat.ST_MODE]
        if mode & stat.S_IXUSR:
            self.is_executable = True
        else:
            self.is_executable = False

        checked_file = open(self.path, "r")
        self.first_line = checked_file.readline()
        checked_file.close()
        self.corrective_actions = []
        self.indentation_exceptions = ['job_unittest.py']


    def _check_indent(self):
        """
        Verifies the file with reindent.py. This tool performs the following
        checks on python files:

          * Trailing whitespaces
          * Tabs
          * End of line
          * Incorrect indentation

        For the purposes of checking, the dry run mode is used and no changes
        are made. It is up to the user to decide if he wants to run reindent
        to correct the issues.
        """
        reindent_raw = utils.system_output('reindent.py -v -d %s | head -1' %
                                           self.path)
        reindent_results = reindent_raw.split(" ")[-1].strip(".")
        if reindent_results == "changed":
            if self.basename not in self.indentation_exceptions:
                self.corrective_actions.append("reindent.py -v %s" % self.path)


    def _check_code(self):
        """
        Verifies the file with run_pylint.py. This tool will call the static
        code checker pylint using the special autotest conventions and warn
        only on problems. If problems are found, a report will be generated.
        Some of the problems reported might be bogus, but it's allways good
        to look at them.
        """
        c_cmd = 'run_pylint.py %s' % self.path
        rc = utils.system(c_cmd, ignore_status=True)
        if rc != 0:
            logging.error("Syntax issues found during '%s'", c_cmd)


    def _check_unittest(self):
        """
        Verifies if the file in question has a unittest suite, if so, run the
        unittest and report on any failures. This is important to keep our
        unit tests up to date.
        """
        if "unittest" not in self.basename:
            stripped_name = self.basename.strip(".py")
            unittest_name = stripped_name + "_unittest.py"
            unittest_path = self.path.replace(self.basename, unittest_name)
            if os.path.isfile(unittest_path):
                unittest_cmd = 'python %s' % unittest_path
                rc = utils.system(unittest_cmd, ignore_status=True)
                if rc != 0:
                    logging.error("Unittest issues found during '%s'",
                                  unittest_cmd)


    def _check_permissions(self):
        """
        Verifies the execution permissions, specifically:
          * Files with no shebang and execution permissions are reported.
          * Files with shebang and no execution permissions are reported.
        """
        if self.first_line.startswith("#!"):
            if not self.is_executable:
                self.corrective_actions.append("svn propset svn:executable ON %s" % self.path)
        else:
            if self.is_executable:
                self.corrective_actions.append("svn propdel svn:executable %s" % self.path)


    def report(self):
        """
        Executes all required checks, if problems are found, the possible
        corrective actions are listed.
        """
        self._check_permissions()
        if self.is_python:
            self._check_indent()
            self._check_code()
            self._check_unittest()
        if self.corrective_actions:
            for action in self.corrective_actions:
                answer = utils.ask("Would you like to execute %s?" % action,
                                   auto=self.confirm)
                if answer == "y":
                    rc = utils.system(action, ignore_status=True)
                    if rc != 0:
                        logging.error("Error executing %s" % action)


class PatchChecker(object):
    def __init__(self, patch=None, patchwork_id=None, confirm=False):
        self.confirm = confirm
        self.base_dir = os.getcwd()
        if patch:
            self.patch = os.path.abspath(patch)
        if patchwork_id:
            self.patch = self._fetch_from_patchwork(patchwork_id)

        if not os.path.isfile(self.patch):
            logging.error("Invalid patch file %s provided. Aborting.",
                          self.patch)
            sys.exit(1)

        self.vcs = VCS()
        changed_files_before = self.vcs.get_modified_files()
        if changed_files_before:
            logging.error("Repository has changed files prior to patch "
                          "application. ")
            answer = utils.ask("Would you like to revert them?", auto=self.confirm)
            if answer == "n":
                logging.error("Not safe to proceed without reverting files.")
                sys.exit(1)
            else:
                for changed_file in changed_files_before:
                    self.vcs.revert_file(changed_file)

        self.untracked_files_before = self.vcs.get_unknown_files()
        self.vcs.update()


    def _fetch_from_patchwork(self, id):
        """
        Gets a patch file from patchwork and puts it under the cwd so it can
        be applied.

        @param id: Patchwork patch id.
        """
        patch_url = "http://patchwork.test.kernel.org/patch/%s/mbox/" % id
        patch_dest = os.path.join(self.base_dir, 'patchwork-%s.patch' % id)
        patch = utils.get_file(patch_url, patch_dest)
        # Patchwork sometimes puts garbage on the path, such as long
        # sequences of underscores (_______). Get rid of those.
        patch_ro = open(patch, 'r')
        patch_contents = patch_ro.readlines()
        patch_ro.close()
        patch_rw = open(patch, 'w')
        for line in patch_contents:
            if not line.startswith("___"):
                patch_rw.write(line)
        patch_rw.close()
        return patch


    def _check_files_modified_patch(self):
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

        for modified_file in modified_files_after:
            # Additional safety check, new commits might introduce
            # new directories
            if os.path.isfile(modified_file):
                file_checker = FileChecker(modified_file)
                file_checker.report()


    def check(self):
        self.vcs.apply_patch(self.patch)
        self._check_files_modified_patch()


if __name__ == "__main__":
    parser = optparse.OptionParser()
    parser.add_option('-p', '--patch', dest="local_patch", action='store',
                      help='path to a patch file that will be checked')
    parser.add_option('-i', '--patchwork-id', dest="id", action='store',
                      help='id of a given patchwork patch')
    parser.add_option('--verbose', dest="debug", action='store_true',
                      help='include debug messages in console output')
    parser.add_option('-f', '--full-check', dest="full_check",
                      action='store_true',
                      help='check the full tree for corrective actions')
    parser.add_option('-y', '--yes', dest="confirm",
                      action='store_true',
                      help='Answer yes to all questions')

    options, args = parser.parse_args()
    local_patch = options.local_patch
    id = options.id
    debug = options.debug
    full_check = options.full_check
    confirm = options.confirm

    logging_manager.configure_logging(CheckPatchLoggingConfig(), verbose=debug)

    ignore_file_list = ['common.py']
    if full_check:
        for root, dirs, files in os.walk('.'):
            if not '.svn' in root:
                for file in files:
                    if file not in ignore_file_list:
                        path = os.path.join(root, file)
                        file_checker = FileChecker(path, confirm=confirm)
                        file_checker.report()
    else:
        if local_patch:
            patch_checker = PatchChecker(patch=local_patch, confirm=confirm)
        elif id:
            patch_checker = PatchChecker(patchwork_id=id, confirm=confirm)
        else:
            logging.error('No patch or patchwork id specified. Aborting.')
            sys.exit(1)
        patch_checker.check()
