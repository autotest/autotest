#!/usr/bin/python

import unittest, os
import common
from autotest_lib.client.common_lib import utils, error
from autotest_lib.client.common_lib.test_utils import mock
from autotest_lib.mirror import rsync

import pdb

class TestRsync(unittest.TestCase):
    def setUp(self):
        self.god = mock.mock_god()

        self.god.stub_function(os, "getpid")
        self.god.stub_function(os.path, "isdir")
        self.god.stub_function(os, "chdir")
        self.god.stub_function(os.path, "exists")
        self.god.stub_function(os, "makedirs")
        self.god.stub_function(os, "remove")
        self.god.stub_function(utils, "system")

        self.prefix = "prefix"
        self.target = "target"


    def tearDown(self):
        self.god.unstub_all()


    def construct_rsync(self):
        # record
        tmpfile = '/tmp/mirror.2'
        os.path.isdir.expect_call(self.target).and_return(False)
        os.makedirs.expect_call(self.target)
        os.getpid.expect_call().and_return(2)
        os.path.exists.expect_call(tmpfile).and_return(True)
        os.remove.expect_call(tmpfile)

        self.rsync = rsync.rsync(self.prefix, self.target)
        self.god.check_playback()


    def test_constructor(self):
        self.construct_rsync()


    def common_sync(self):
        self.construct_rsync()

        self.src = "src"
        self.dest = "dest"

        # record
        os.chdir.expect_call(self.target)
        os.path.isdir.expect_call(self.dest).and_return(False)
        os.makedirs.expect_call(self.dest)
        new_src = os.path.join(self.prefix, self.src)
        return self.rsync.command + (' %s "%s" "%s"'
                                     % (self.rsync.exclude, new_src, self.dest))


    def test_sync(self):
        cmd = self.common_sync()
        utils.system.expect_call(cmd + ' >> %s 2>&1' % self.rsync.tmpfile)

        self.rsync.sync(self.src, self.dest)
        self.god.check_playback()


    def test_sync_and_raise(self):
        cmd = self.common_sync()

        cmdError = error.CmdError(cmd + ' >> %s 2>&1', None)
        utils.system.expect_call(cmd + ' >> %s 2>&1'
                             % self.rsync.tmpfile).and_raises(cmdError)

        failure = True
        try:
            self.rsync.sync(self.src, self.dest)
        except error.CmdError:
            failure = False

        self.god.check_playback()
        self.assertFalse(failure)


if __name__ == "__main__":
    unittest.main()
