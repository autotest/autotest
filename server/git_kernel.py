"""
This module defines the GitKernel class

@author: Ryan Harper (ryanh@us.ibm.com)
@copyright: IBM 2007
"""

import os, logging
import git, source_kernel


class GitKernel(git.InstallableGitRepo):
    """
    This class represents an installable git kernel repo.

    It is used to pull down a local copy of a git repo, check if the local repo
    is up-to-date, if not update and then build the kernel from the git repo.
    """
    def __init__(self, repodir, giturl, weburl=None):
        super(GitKernel, self).__init__(repodir, giturl, weburl)
        self._patches = []
        self._config = None
        self._build = None
        self._branch = None
        self._revision = None


    def configure(self, config):
        self._config = config


    def patch(self, patch):
        self._patches.append(patch)


    def checkout(self, revision, local=None):
        """
        Checkout the commit id, branch, or tag.

        @param revision: Name of the git remote branch, revision or tag
        @param local: Name of the local branch, implies -b
        """
        logging.info('Checking out %s', revision)
        super(GitKernel, self).checkout(revision)
        self._revision = super(GitKernel, self).get_revision()
        self._branch = super(GitKernel, self).get_branch()
        logging.info('Checked out %s on branch %s', self._revision,
                     self._branch)


    def show_branch(self):
        """
        Print the current local branch name.
        """
        self._branch = super(GitKernel, self).get_branch()
        logging.info(self._branch)


    def show_branches(self, all=True):
        """
        Print the local and remote branches.

        @param all: Whether to show all branches (True) or only local branches
                (False).
        """
        self._branch = super(GitKernel, self).get_branch()
        logging.info(super(GitKernel, self).get_branch(all=all))


    def show_revision(self):
        """
        Show the current git revision.
        """
        self._revision = super(GitKernel, self).get_revision()
        logging.info(self._revision)


    def install(self, host, build=True, builddir=None, revision=None):
        """
        Install the git tree in a host.

        @param host: Host object
        @param build: Whether to build the source tree
        @param builddir: Specify a build dir. If no build dir is specified,
                the job temporary directory will be used, so the build won't
                be persistent.
        @param revision: Desired commit hash. If ommited, will build from HEAD
                of the branch.
        """
        if revision:
            self.checkout(revision)
            self._revision = super(GitKernel, self).get_revision()
            logging.info('Checked out revision: %s', self._revision)

        if not builddir:
            self._build = os.path.join(host.get_tmp_dir(), "build")
            logging.warning('Builddir %s is not persistent (it will be erased '
                            'in future jobs)', self._build)
        else:
            self._build = builddir

        # push source to host for install
        logging.info('Pushing %s to host', self.source_material)
        host.send_file(self.source_material, self._build)
        remote_source_material= os.path.join(self._build,
                                        os.path.basename(self.source_material))

        # use a source_kernel to configure, patch, build and install.
        sk = source_kernel.SourceKernel(remote_source_material)

        if build:
            # apply patches
            for p in self._patches:
                sk.patch(p)

            # configure
            sk.configure(self._config)

            # build
            sk.build(host)

        # install
        sk.install(host)
