"""
Code that helps to deal with content from git repositories
"""


import os
import logging
import error
from autotest.client import utils, os_dep


__all__ = ["GitRepoHelper", "get_repo"]


class GitRepoHelper(object):

    '''
    Helps to deal with git repos, mostly fetching content from a repo
    '''

    def __init__(self, uri, branch='master', lbranch='master', commit=None,
                 destination_dir=None, base_uri=None):
        '''
        Instantiates a new GitRepoHelper

        :type uri: string
        :param uri: git repository url
        :type branch: string
        :param branch: git remote branch
        :type destination_dir: string
        :param destination_dir: path of a dir where to save downloaded code
        :type commit: string
        :param commit: specific commit to download
        :type lbranch: string
        :param lbranch: git local branch name, if different from remote
        :type base_uri: string
        :param base_uri: a closer, usually local, git repository url from where to
                    fetch content first
        '''
        self.uri = uri
        self.base_uri = base_uri
        self.branch = branch
        self.commit = commit

        if destination_dir is None:
            uri_basename = uri.split("/")[-1]
            self.destination_dir = os.path.join("/tmp", uri_basename)
        else:
            self.destination_dir = destination_dir
        if lbranch is None:
            self.lbranch = branch
        else:
            self.lbranch = lbranch

        self.cmd = os_dep.command('git')

    def init(self):
        '''
        Initializes a directory for receiving a verbatim copy of git repo

        This creates a directory if necessary, and either resets or inits
        the repo
        '''
        if not os.path.exists(self.destination_dir):
            logging.debug('Creating directory %s for git repo %s',
                          self.destination_dir, self.uri)
            os.makedirs(self.destination_dir)

        os.chdir(self.destination_dir)
        if os.path.exists('.git'):
            logging.debug('Resetting previously existing git repo at %s for '
                          'receiving git repo %s',
                          self.destination_dir, self.uri)
            self.git_cmd('reset --hard')
        else:
            logging.debug('Initializing new git repo at %s for receiving '
                          'git repo %s',
                          self.destination_dir, self.uri)
            self.git_cmd('init')

    def git_cmd(self, cmd, ignore_status=False):
        '''
        Wraps git commands.

        :param cmd: Command to be executed.
        :param ignore_status: Whether we should suppress error.CmdError
                exceptions if the command did return exit code !=0 (True), or
                not suppress them (False).
        '''
        os.chdir(self.destination_dir)
        return utils.run(r"%s %s" % (self.cmd, utils.sh_escape(cmd)),
                         ignore_status=ignore_status)

    def fetch(self, uri):
        '''
        Performs a git fetch from the remote repo
        '''
        logging.info("Fetching git [REP '%s' BRANCH '%s'] -> %s",
                     uri, self.branch, self.destination_dir)
        self.git_cmd("fetch -q -f -u -t %s %s:%s" %
                     (uri, self.branch, self.lbranch))

    def get_top_commit(self):
        '''
        Returns the topmost commit id for the current branch.

        :return: Commit id.
        '''
        return self.git_cmd('log --pretty=format:%H -1').stdout.strip()

    def get_top_tag(self):
        '''
        Returns the topmost tag for the current branch.

        :return: Tag.
        '''
        try:
            return self.git_cmd('describe').stdout.strip()
        except error.CmdError:
            return None

    def checkout(self, branch=None, commit=None):
        '''
        Performs a git checkout for a given branch and start point (commit)

        :param branch: Remote branch name.
        :param commit: Specific commit hash.
        '''
        if branch is None:
            branch = self.branch

        logging.debug('Checking out branch %s', branch)
        self.git_cmd("checkout %s" % branch)

        if commit is None:
            commit = self.commit

        if commit is not None:
            logging.debug('Checking out commit %s', self.commit)
            self.git_cmd("checkout %s" % self.commit)
        else:
            logging.debug('Specific commit not specified')

        top_commit = self.get_top_commit()
        top_tag = self.get_top_tag()
        if top_tag is None:
            top_tag_desc = 'no tag found'
        else:
            top_tag_desc = 'tag %s' % top_tag
        logging.info("git commit ID is %s (%s)", top_commit, top_tag_desc)

    def execute(self):
        '''
        Performs all steps necessary to initialize and download a git repo.

        This includes the init, fetch and checkout steps in one single
        utility method.
        '''
        self.init()
        if self.base_uri is not None:
            self.fetch(self.base_uri)
        self.fetch(self.uri)
        self.checkout()


def get_repo(uri, branch='master', lbranch='master', commit=None,
             destination_dir=None, base_uri=None):
    """
    Utility function that retrieves a given git code repository.

    :type uri: string
    :param uri: git repository url
    :type branch: string
    :param branch: git remote branch
    :type destination_dir: string
    :param destination_dir: path of a dir where to save downloaded code
    :type commit: string
    :param commit: specific commit to download
    :type lbranch: string
    :param lbranch: git local branch name, if different from remote
    :type base_uri: string
    :param uri: a closer, usually local, git repository url from where to
                fetch content first from
    """
    repo = GitRepoHelper(uri, branch, lbranch, commit, destination_dir,
                         base_uri)
    repo.execute()
    return repo.destination_dir
