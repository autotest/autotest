#
# Copyright 2007 IBM Corp. Released under the GPL v2
# Authors: Ryan Harper <ryanh@us.ibm.com>
#

"""
This module defines the GitKernel class
"""

__author__ = """
ryanh@us.ibm.com (Ryan Harper)
"""


import os
import git, source_kernel


class GitKernel(git.GitRepo):
    """
    This class represents a git kernel repo.

    It is used to pull down a local copy of a git repo, check if the local repo
    is up-to-date, if not update and then build the kernel from the git repo.
    """
    def __init__(self, repodir, giturl, weburl):
        git.GitRepo.__init__(self, repodir, giturl, weburl)
        self.__patches = []
        self.__config = None
        self.__build = None
        self.__branch = None
        self.__revision = None


    def configure(self, config):
        self.__config = config


    def patch(self, patch):
        self.__patches.append(patch)


    def checkout(self, revision, local=None):
        """
        Checkout the commit id, branch, or tag

        revision:str - name of the git remote branch, revision or tag
        local:str - name of the local branch, implies -b
        """
        print 'checking out %s' % revision
        super(GitKernel, self).checkout(revision)
        self.__revision = super(GitKernel, self).get_revision()
        self.__branch = super(GitKernel, self).get_branch()
        print 'checked out %s on branch %s' % (self.__revision, self.__branch)

    def show_branch(self):
        """
        Print the current local branch name
        """
        self.__branch = super(GitKernel, self).get_branch()
        print self.__branch


    def show_branches(self, all=True):
        """
        Print the local and remote branches
        """
        self.__branch = super(GitKernel, self).get_branch()
        print super(GitKernel, self).get_branch(all=all)


    def show_revision(self):
        """
        Show the current git revision
        """
        self.__revision = super(GitKernel, self).get_revision()
        print self.__revision


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
            self.__revision = super(GitKernel, self).get_revision()
            print 'checked out revision: %s' %(self.__revision)

        if not builddir:
            self.__build = os.path.join(host.get_tmp_dir(),"build")
            print 'warning: builddir %s is not persistent' %(self.__build)

        # push source to host for install
        print 'pushing %s to host' % self.source_material
        host.send_file(self.source_material, self.__build)
        remote_source_material= os.path.join(self.__build,
                                        os.path.basename(self.source_material))

        # use a source_kernel to configure, patch, build and install.
        sk = source_kernel.SourceKernel(remote_source_material)

        if build:
            # apply patches
            for p in self.__patches:
                sk.patch(p)

            # configure
            sk.configure(self.__config)

            # build
            sk.build(host)

        # install
        sk.install(host)
