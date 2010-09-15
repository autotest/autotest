"""
This module defines a class for handling building from git repos

@author: Ryan Harper (ryanh@us.ibm.com)
@copyright: IBM 2007
"""

import os, warnings, logging
from autotest_lib.client.common_lib import error, revision_control
from autotest_lib.client.bin import os_dep
from autotest_lib.server import utils, installable_object


class InstallableGitRepo(installable_object.InstallableObject):
    """
    This class helps to pick a git repo and install it in a host.
    """
    def __init__(self, repodir, giturl, weburl=None):
        self.repodir = repodir
        self.giturl = giturl
        self.weburl = weburl
        self.git_repo = revision_control.GitRepo(self.repodir, self.giturl,
                                                 self.weburl)
        # default to same remote path as local
        self._build = os.path.dirname(self.repodir)


    # base install method
    def install(self, host, builddir=None):
        """
        Install a git repo in a host. It works by pushing the downloaded source
        code to the host.

        @param host: Host object.
        @param builddir: Directory on the host filesystem that will host the
                source code.
        """
        # allow override of target remote dir
        if builddir:
            self._build = builddir

        # push source to host for install
        logging.info('Pushing code dir %s to host %s', self.source_material,
                     self._build)
        host.send_file(self.source_material, self._build)


    def gitcmd(self, cmd, ignore_status=False):
        """
        Wrapper for a git command.

        @param cmd: Git subcommand (ex 'clone').
        @param ignore_status: Whether we should supress error.CmdError
                exceptions if the command did return exit code !=0 (True), or
                not supress them (False).
        """
        return self.git_repo.gitcmd(cmd, ignore_status)


    def get(self, **kwargs):
        """
        This method overrides baseclass get so we can do proper git
        clone/pulls, and check for updated versions.  The result of
        this method will leave an up-to-date version of git repo at
        'giturl' in 'repodir' directory to be used by build/install
        methods.

        @param **kwargs: Dictionary of parameters to the method get.
        """
        self.source_material = self.repodir
        return self.git_repo.get(**kwargs)


    def get_local_head(self):
        """
        Get the top commit hash of the current local git branch.

        @return: Top commit hash of local git branch
        """
        return self.git_repo.get_local_head()


    def get_remote_head(self):
        """
        Get the top commit hash of the current remote git branch.

        @return: Top commit hash of remote git branch
        """
        return self.git_repo.get_remote_head()


    def is_out_of_date(self):
        """
        Return whether this branch is out of date with regards to remote branch.

        @return: False, if the branch is outdated, True if it is current.
        """
        return self.git_repo.is_out_of_date()


    def is_repo_initialized(self):
        """
        Return whether the git repo was already initialized (has a top commit).

        @return: False, if the repo was initialized, True if it was not.
        """
        return self.git_repo.is_repo_initialized()


    def get_revision(self):
        """
        Return current HEAD commit id
        """
        return self.git_repo.get_revision()


    def checkout(self, remote, local=None):
        """
        Check out the git commit id, branch, or tag given by remote.

        Optional give the local branch name as local.

        @param remote: Remote commit hash
        @param local: Local commit hash
        @note: For git checkout tag git version >= 1.5.0 is required
        """
        return self.git_repo.checkout(remote, local)


    def get_branch(self, all=False, remote_tracking=False):
        """
        Show the branches.

        @param all: List both remote-tracking branches and local branches (True)
                or only the local ones (False).
        @param remote_tracking: Lists the remote-tracking branches.
        """
        return self.git_repo.get_branch(all, remote_tracking)
