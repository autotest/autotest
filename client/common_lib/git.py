"""
Code that helps to deal with content from git repositories
"""


import os, logging
from autotest_lib.client.bin import utils
from autotest_lib.client.common_lib import error


__all__ = ["GitRepoHelper", "get_git_branch"]


class GitRepoHelper(object):
    '''
    Helps to deal with git repos, mostly fetching content from a repo
    '''
    def __init__(self, uri, branch, destination_dir, commit=None, lbranch=None,
                 base_uri=None):
        '''
        Instantiates a new GitRepoHelper

        @type uri: string
        @param uri: git repository url
        @type branch: string
        @param branch: git remote branch
        @type destination_dir: string
        @param destination_dir: path of a dir where to save downloaded code
        @type commit: string
        @param commit: specific commit to download
        @type lbranch: string
        @param lbranch: git local branch name, if different from remote
        @type base_uri: string
        @param uri: a closer, usually local, git repository url from where to
                    fetch content first from
        '''
        self.uri = uri
        self.base_uri = base_uri
        self.branch = branch
        self.destination_dir = destination_dir
        self.commit = commit
        if lbranch is None:
            self.lbranch = branch


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
            utils.system('git reset --hard')
        else:
            logging.debug('Initializing new git repo at %s for receiving '
                          'git repo %s',
                          self.destination_dir, self.uri)
            utils.system('git init')


    def fetch(self, uri):
        '''
        Performs a git fetch from the remote repo
        '''
        logging.info("Fetching git [REP '%s' BRANCH '%s'] -> %s",
                     uri, self.branch, self.destination_dir)
        os.chdir(self.destination_dir)
        utils.system("git fetch -q -f -u -t %s %s:%s" % (uri,
                                                         self.branch,
                                                         self.lbranch))


    def checkout(self):
        '''
        Performs a git checkout for a given branch and start point (commit)
        '''
        os.chdir(self.destination_dir)

        logging.debug('Checking out local branch %s', self.lbranch)
        utils.system("git checkout %s" % self.lbranch)

        if self.commit:
            logging.debug('Checking out commit %s', self.commit)
            utils.system("git checkout %s" % self.commit)
        else:
            logging.debug('Specific commit not specified')

        h = utils.system_output('git log --pretty=format:"%H" -1').strip()
        try:
            desc = "tag %s" % utils.system_output("git describe")
        except error.CmdError:
            desc = "no tag found"

        logging.info("git commit hash is %s (%s)", h, desc)


    def execute(self):
        '''
        Performs all steps necessary to initialize and download a git repo

        This includes the init, fetch and checkout steps in one single
        utility method.
        '''
        self.init()
        if self.base_uri is not None:
            self.fetch(self.base_uri)
        self.fetch(self.uri)
        self.checkout()


def get_git_branch(uri, branch, destination_dir, commit=None, lbranch=None,
                   base_uri=None):
    """
    Utility function that retrieves a given git code repository.

    @type uri: string
    @param uri: git repository url
    @type branch: string
    @param branch: git remote branch
    @type destination_dir: string
    @param destination_dir: path of a dir where to save downloaded code
    @type commit: string
    @param commit: specific commit to download
    @type lbranch: string
    @param lbranch: git local branch name, if different from remote
    @type base_uri: string
    @param uri: a closer, usually local, git repository url from where to
                fetch content first from
    """
    git = GitRepoHelper(uri, branch, destination_dir, commit, lbranch,
                        base_uri)
    git.execute()
    return destination_dir


