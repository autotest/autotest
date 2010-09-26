"""
Module with abstraction layers to revision control systems.

With this library, autotest developers can handle source code checkouts and
updates on both client as well as server code.
"""

import os, warnings, logging
import error, utils
from autotest_lib.client.bin import os_dep


class GitRepo(object):
    """
    This class represents a git repo.

    It is used to pull down a local copy of a git repo, check if the local
    repo is up-to-date, if not update.  It delegates the install to
    implementation classes.
    """

    def __init__(self, repodir, giturl, weburl=None):
        if repodir is None:
            raise ValueError('You must provide a path that will hold the'
                             'git repository')
        self.repodir = utils.sh_escape(repodir)
        if giturl is None:
            raise ValueError('You must provide a git URL repository')
        self.giturl = giturl
        if weburl is not None:
            warnings.warn("Param weburl: You are no longer required to provide "
                          "a web URL for your git repos", DeprecationWarning)

        # path to .git dir
        self.gitpath = utils.sh_escape(os.path.join(self.repodir,'.git'))

        # Find git base command. If not found, this will throw an exception
        git_base_cmd = os_dep.command('git')

        # base git command , pointing to gitpath git dir
        self.gitcmdbase = '%s --git-dir=%s' % (git_base_cmd, self.gitpath)

        # default to same remote path as local
        self._build = os.path.dirname(self.repodir)


    def _run(self, command, timeout=None, ignore_status=False):
        """
        Auxiliary function to run a command, with proper shell escaping.

        @param timeout: Timeout to run the command.
        @param ignore_status: Whether we should supress error.CmdError
                exceptions if the command did return exit code !=0 (True), or
                not supress them (False).
        """
        return utils.run(r'%s' % (utils.sh_escape(command)),
                         timeout, ignore_status)


    def gitcmd(self, cmd, ignore_status=False):
        """
        Wrapper for a git command.

        @param cmd: Git subcommand (ex 'clone').
        @param ignore_status: Whether we should supress error.CmdError
                exceptions if the command did return exit code !=0 (True), or
                not supress them (False).
        """
        cmd = '%s %s' % (self.gitcmdbase, cmd)
        return self._run(cmd, ignore_status=ignore_status)


    def get(self, **kwargs):
        """
        This method overrides baseclass get so we can do proper git
        clone/pulls, and check for updated versions.  The result of
        this method will leave an up-to-date version of git repo at
        'giturl' in 'repodir' directory to be used by build/install
        methods.

        @param **kwargs: Dictionary of parameters to the method get.
        """
        if not self.is_repo_initialized():
            # this is your first time ...
            logging.info('Cloning git repo %s', self.giturl)
            cmd = 'clone %s %s ' % (self.giturl, self.repodir)
            rv = self.gitcmd(cmd, True)
            if rv.exit_status != 0:
                logging.error(rv.stderr)
                raise error.CmdError('Failed to clone git url', rv)
            else:
                logging.info(rv.stdout)

        else:
            # exiting repo, check if we're up-to-date
            if self.is_out_of_date():
                logging.info('Updating git repo %s', self.giturl)
                rv = self.gitcmd('pull', True)
                if rv.exit_status != 0:
                    logging.error(rv.stderr)
                    e_msg = 'Failed to pull git repo data'
                    raise error.CmdError(e_msg, rv)
            else:
                logging.info('repo up-to-date')

        # remember where the source is
        self.source_material = self.repodir


    def get_local_head(self):
        """
        Get the top commit hash of the current local git branch.

        @return: Top commit hash of local git branch
        """
        cmd = 'log --pretty=format:"%H" -1'
        l_head_cmd = self.gitcmd(cmd)
        return l_head_cmd.stdout.strip()


    def get_remote_head(self):
        """
        Get the top commit hash of the current remote git branch.

        @return: Top commit hash of remote git branch
        """
        cmd1 = 'remote show'
        origin_name_cmd = self.gitcmd(cmd1)
        cmd2 = 'log --pretty=format:"%H" -1 ' + origin_name_cmd.stdout.strip()
        r_head_cmd = self.gitcmd(cmd2)
        return r_head_cmd.stdout.strip()


    def is_out_of_date(self):
        """
        Return whether this branch is out of date with regards to remote branch.

        @return: False, if the branch is outdated, True if it is current.
        """
        local_head = self.get_local_head()
        remote_head = self.get_remote_head()

        # local is out-of-date, pull
        if local_head != remote_head:
            return True

        return False


    def is_repo_initialized(self):
        """
        Return whether the git repo was already initialized (has a top commit).

        @return: False, if the repo was initialized, True if it was not.
        """
        cmd = 'log --max-count=1'
        rv = self.gitcmd(cmd, True)
        if rv.exit_status == 0:
            return True

        return False


    def get_revision(self):
        """
        Return current HEAD commit id
        """
        if not self.is_repo_initialized():
            self.get()

        cmd = 'rev-parse --verify HEAD'
        gitlog = self.gitcmd(cmd, True)
        if gitlog.exit_status != 0:
            logging.error(gitlog.stderr)
            raise error.CmdError('Failed to find git sha1 revision', gitlog)
        else:
            return gitlog.stdout.strip('\n')


    def checkout(self, remote, local=None):
        """
        Check out the git commit id, branch, or tag given by remote.

        Optional give the local branch name as local.

        @param remote: Remote commit hash
        @param local: Local commit hash
        @note: For git checkout tag git version >= 1.5.0 is required
        """
        if not self.is_repo_initialized():
            self.get()

        assert(isinstance(remote, basestring))
        if local:
            cmd = 'checkout -b %s %s' % (local, remote)
        else:
            cmd = 'checkout %s' % (remote)
        gitlog = self.gitcmd(cmd, True)
        if gitlog.exit_status != 0:
            logging.error(gitlog.stderr)
            raise error.CmdError('Failed to checkout git branch', gitlog)
        else:
            logging.info(gitlog.stdout)


    def get_branch(self, all=False, remote_tracking=False):
        """
        Show the branches.

        @param all: List both remote-tracking branches and local branches (True)
                or only the local ones (False).
        @param remote_tracking: Lists the remote-tracking branches.
        """
        if not self.is_repo_initialized():
            self.get()

        cmd = 'branch --no-color'
        if all:
            cmd = " ".join([cmd, "-a"])
        if remote_tracking:
            cmd = " ".join([cmd, "-r"])

        gitlog = self.gitcmd(cmd, True)
        if gitlog.exit_status != 0:
            logging.error(gitlog.stderr)
            raise error.CmdError('Failed to get git branch', gitlog)
        elif all or remote_tracking:
            return gitlog.stdout.strip('\n')
        else:
            branch = [b[2:] for b in gitlog.stdout.split('\n')
                      if b.startswith('*')][0]
            return branch
