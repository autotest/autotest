"""
This module defines the GitKernel class.
"""

import logging
import os

from autotest.client.shared import git

import source_kernel


class GitKernel(git.GitRepoHelper):

    """
    This class represents an installable git kernel repo.

    It will fetch a git repo and copy its contents over to a client, so
    it can be built as a normal source kernel.
    """

    def __init__(self, uri, branch='master', lbranch='master', commit=None,
                 destination_dir=None, base_uri=None,
                 remote_destination_dir=None, patches=[], config=None):
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
        :param base_uri: a closer, usually local, git repository url from where
                         to fetch content first from.

        :param remote_destination_dir: To where the source code will be copied
                    on the client
        :param patches: List of patches to be applied on top of this kernel
        :param config: Config to pass to the kernel
        '''
        super(GitKernel, self).__init__(uri=uri, branch=branch, lbranch=lbranch,
                                        commit=commit,
                                        destination_dir=destination_dir,
                                        base_uri=base_uri)

        if remote_destination_dir is None:
            self.remote_destination_dir = self.destination_dir
        else:
            self.remote_destination_dir = remote_destination_dir
        self.patches = patches
        self.config = config

    def install(self, host, build=True, branch=None, commit=None):
        """
        Install the git tree in a host.

        :param host: Host object.
        :param build: Whether to build the source tree.
        :param branch: Check out this specific branch before building.
        :param commit: Check out this specific commit before building.
        """
        self.execute()
        if (branch is not None) or (commit is not None):
            self.checkout(branch=branch, commit=commit)

        # push source to host for install
        logging.info('Pushing %s to client', self.destination_dir)
        host.send_file(self.destination_dir,
                       os.path.dirname(self.remote_destination_dir))

        # use a source_kernel to configure, patch, build and install.
        sk = source_kernel.SourceKernel(self.remote_destination_dir)

        if build:
            # apply patches
            for p in self.patches:
                sk.patch(p)

            # configure
            sk.configure(self.config)

            # build
            sk.build(host)

        # install
        sk.install(host)
