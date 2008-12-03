#
# Copyright 2007 IBM Corp. Released under the GPL v2
# Authors: Ryan Harper <ryanh@us.ibm.com>
#

"""
This module defines a class for handling building from git repos
"""

__author__ = """
ryanh@us.ibm.com (Ryan Harper)
"""


import os
from autotest_lib.client.common_lib import error
from autotest_lib.server import utils, installable_object


class GitRepo(installable_object.InstallableObject):
    """
    This class represents a git repo.

    It is used to pull down a local copy of a git repo, check if the local
    repo is up-to-date, if not update.  It delegates the install to
    implementation classes.

    """

    def __init__(self, repodir, giturl, weburl):
        super(installable_object.InstallableObject, self).__init__()
        if repodir is None:
            e_msg = 'You must provide a directory to hold the git repository'
            raise ValueError(e_msg)
        self.repodir = utils.sh_escape(repodir)
        if giturl is None:
            raise ValueError('You must provide a git URL to the repository')
        self.giturl = giturl
        if weburl is None:
            raise ValueError('You must provide a http URL to the repository')
        self.weburl = weburl

        # path to .git dir
        self.gitpath = utils.sh_escape(os.path.join(self.repodir,'.git'))

        # base git command , pointing to gitpath git dir
        self.gitcmdbase = 'git --git-dir=%s' % self.gitpath

        # default to same remote path as local
        self.__build = os.path.dirname(self.repodir)


    def run(self, command, timeout=None, ignore_status=False):
        return utils.run(r'%s' % (utils.sh_escape(command)),
                          timeout, ignore_status)


    # base install method
    def install(self, host, builddir=None):
        # allow override of target remote dir
        if builddir:
            self.__build = builddir

        # push source to host for install
        print 'pushing %s to host:%s' %(self.source_material, self.__build)
        host.send_file(self.source_material, self.__build)


    def gitcmd(self, cmd, ignore_status=False):
        return self.run('%s %s'%(self.gitcmdbase, cmd),
                                        ignore_status=ignore_status)


    def get(self, **kwargs):
        """
        This method overrides baseclass get so we can do proper git
        clone/pulls, and check for updated versions.  The result of
        this method will leave an up-to-date version of git repo at
        'giturl' in 'repodir' directory to be used by build/install
        methods.
        """

        if not self.is_repo_initialized():
            # this is your first time ...
            print 'cloning repo...'
            cmd = 'clone %s %s ' %(self.giturl, self.repodir)
            rv = self.gitcmd(cmd, True)
            if rv.exit_status != 0:
                print rv.stderr
                raise error.CmdError('Failed to clone git url', rv)
            else:
                print rv.stdout

        else:
            # exiting repo, check if we're up-to-date
            if self.is_out_of_date():
                print 'updating repo...'
                rv = self.gitcmd('pull', True)
                if rv.exit_status != 0:
                    print rv.stderr
                    e_msg = 'Failed to pull git repo data'
                    raise error.CmdError(e_msg, rv)
            else:
                print 'repo up-to-date'


        # remember where the source is
        self.source_material = self.repodir


    def get_local_head(self):
        cmd = 'log --max-count=1'
        gitlog = self.gitcmd(cmd).stdout

        # parsing the commit checksum out of git log 's first entry.
        # Output looks like:
        #
        #       commit 1dccba29b4e5bf99fb98c324f952386dda5b097f
        #       Merge: 031b69b... df6af41...
        #       Author: Avi Kivity <avi@qumranet.com>
        #       Date:   Tue Oct 23 10:36:11 2007 +0200
        #
        #           Merge home:/home/avi/kvm/linux-2.6
        return str(gitlog.split('\n')[0]).split()[1]


    def get_remote_head(self):
        def __needs_refresh(lines):
            tag = '<meta http-equiv="refresh" content="0"/>'
            if len(filter(lambda x: x.startswith(tag), lines)) > 0:
                return True

            return False


        # scan git web interface for revision HEAD's commit tag
        gitwebaction=';a=commit;h=HEAD'
        url = self.weburl+gitwebaction
        max_refresh = 4
        r = 0

        print 'checking %s for changes' %(url)
        u = utils.urlopen(url)
        lines = u.read().split('\n')

        while __needs_refresh(lines) and r < max_refresh:
            print 'refreshing url'
            r = r+1
            u = utils.urlopen(url)
            lines = u.read().split('\n')

        if r >= max_refresh:
            e_msg = 'Failed to get remote repo status, refreshed %s times' % r
            raise IndexError(e_msg)

        # looking for a line like:
        # <tr><td>commit</td><td # class="sha1">aadea67210c8b9e7a57744a1c2845501d2cdbac7</td></tr>
        commit_filter = lambda x: x.startswith('<tr><td>commit</td>')
        commit_line = filter(commit_filter, lines)

        # extract the sha1 sum from the commit line
        return str(commit_line).split('>')[4].split('<')[0]


    def is_out_of_date(self):
        local_head = self.get_local_head()
        remote_head = self.get_remote_head()

        # local is out-of-date, pull
        if local_head != remote_head:
            return True

        return False


    def is_repo_initialized(self):
        # if we fail to get a rv of 0 out of the git log command
        # then the repo is bogus

        cmd = 'log --max-count=1'
        rv = self.gitcmd(cmd, True)
        if rv.exit_status == 0:
            return True

        return False
