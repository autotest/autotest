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


    def configure(self, config):
        self.__config = config


    def patch(self, patch):
        self.__patches.append(patch)


    def install(self, host, build=True, builddir=None):
        # use tmpdir if no builddir specified
        # NB: pass a builddir to install() method if you
        # need to ensure the build remains after the completion
        # of a job
        if not builddir:
            self.__build = os.path.join(host.get_tmp_dir(),"build")
            print 'warning: builddir %s is not persistent' %(self.__build)

        # push source to host for install
        print 'pushing %s to host' %(self.source_material)
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
