#!/usr/bin/python

import os
import common

from autotest_lib.client.common_lib.test_utils import mock, unittest
from autotest_lib.client.common_lib import autotemp
from autotest_lib.client.bin import local_host


class test_local_host_class(unittest.TestCase):
    def setUp(self):
        self.god = mock.mock_god()
        self.god.stub_function(local_host.utils, 'run')

        self.tmpdir = autotemp.tempdir(unique_id='localhost_unittest')


    def tearDown(self):
        self.god.unstub_all()
        self.tmpdir.clean()


    def test_init(self):
        self.god.stub_function(local_host.platform, 'node')
        local_host.platform.node.expect_call().and_return('foo')

        # run the actual test
        host = local_host.LocalHost()
        self.assertEqual(host.hostname, 'foo')
        self.god.check_playback()

        host = local_host.LocalHost(hostname='bar')
        self.assertEqual(host.hostname, 'bar')
        self.god.check_playback()


    def test_wait_up(self):
        # just test that wait_up always works
        host = local_host.LocalHost()
        host.wait_up(1)
        self.god.check_playback()


    def _setup_run(self, result):
        host = local_host.LocalHost()

        (local_host.utils.run.expect_call(result.command, timeout=123,
                ignore_status=True, stdout_tee=local_host.utils.TEE_TO_LOGS,
                stderr_tee=local_host.utils.TEE_TO_LOGS, stdin=None, args=())
                .and_return(result))

        return host


    def test_run_success(self):
        result = local_host.utils.CmdResult(command='yes', stdout='y',
                stderr='', exit_status=0, duration=1)

        host = self._setup_run(result)

        self.assertEqual(host.run('yes', timeout=123, ignore_status=True,
                stdout_tee=local_host.utils.TEE_TO_LOGS,
                stderr_tee=local_host.utils.TEE_TO_LOGS, stdin=None), result)
        self.god.check_playback()


    def test_run_failure_raised(self):
        result = local_host.utils.CmdResult(command='yes', stdout='',
                stderr='err', exit_status=1, duration=1)

        host = self._setup_run(result)

        self.assertRaises(local_host.error.AutotestHostRunError, host.run,
                          'yes', timeout=123)
        self.god.check_playback()


    def test_run_failure_ignored(self):
        result = local_host.utils.CmdResult(command='yes', stdout='',
                stderr='err', exit_status=1, duration=1)

        host = self._setup_run(result)

        self.assertEqual(host.run('yes', timeout=123, ignore_status=True),
                         result)
        self.god.check_playback()


    def test_list_files_glob(self):
        host = local_host.LocalHost()

        files = (os.path.join(self.tmpdir.name, 'file1'),
                 os.path.join(self.tmpdir.name, 'file2'))

        # create some files in tmpdir
        open(files[0], 'w').close()
        open(files[1], 'w').close()

        self.assertSameElements(
                files,
                host.list_files_glob(os.path.join(self.tmpdir.name, '*')))


    def test_symlink_closure_does_not_add_existent_file(self):
        host = local_host.LocalHost()

        # create a file and a symlink to it
        fname = os.path.join(self.tmpdir.name, 'file')
        sname = os.path.join(self.tmpdir.name, 'sym')
        open(fname, 'w').close()
        os.symlink(fname, sname)

        # test that when the symlinks point to already know files
        # nothing is added
        self.assertSameElements(
                [fname, sname],
                host.symlink_closure([fname, sname]))


    def test_symlink_closure_adds_missing_files(self):
        host = local_host.LocalHost()

        # create a file and a symlink to it
        fname = os.path.join(self.tmpdir.name, 'file')
        sname = os.path.join(self.tmpdir.name, 'sym')
        open(fname, 'w').close()
        os.symlink(fname, sname)

        # test that when the symlinks point to unknown files they are added
        self.assertSameElements(
                [fname, sname],
                host.symlink_closure([sname]))


if __name__ == "__main__":
    unittest.main()
