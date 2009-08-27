#!/usr/bin/python
# Copyright 2009 Google Inc. Released under the GPL v2

import unittest

import common
from autotest_lib.client.common_lib.test_utils import mock
from autotest_lib.server import subcommand


def _create_subcommand(func, args):
    # to avoid __init__
    class wrapper(subcommand.subcommand):
        def __init__(self, func, args):
            self.func = func
            self.args = args
            self.subdir = None
            self.debug = None
            self.pid = None
            self.returncode = None
            self.lambda_function = lambda: func(*args)

    return wrapper(func, args)


class subcommand_test(unittest.TestCase):
    def setUp(self):
        self.god = mock.mock_god()


    def tearDown(self):
        self.god.unstub_all()
        # cleanup the hooks
        subcommand.subcommand.fork_hooks = []
        subcommand.subcommand.join_hooks = []


    def test_create(self):
        def check_attributes(cmd, func, args, subdir=None, debug=None,
                             pid=None, returncode=None, fork_hooks=[],
                             join_hooks=[]):
            self.assertEquals(cmd.func, func)
            self.assertEquals(cmd.args, args)
            self.assertEquals(cmd.subdir, subdir)
            self.assertEquals(cmd.debug, debug)
            self.assertEquals(cmd.pid, pid)
            self.assertEquals(cmd.returncode, returncode)
            self.assertEquals(cmd.fork_hooks, fork_hooks)
            self.assertEquals(cmd.join_hooks, join_hooks)

        def func(arg1, arg2):
            pass

        cmd = subcommand.subcommand(func, (2, 3))
        check_attributes(cmd, func, (2, 3))
        self.god.check_playback()

        self.god.stub_function(subcommand.os.path, 'abspath')
        self.god.stub_function(subcommand.os.path, 'exists')
        self.god.stub_function(subcommand.os, 'mkdir')

        subcommand.os.path.abspath.expect_call('dir').and_return('/foo/dir')
        subcommand.os.path.exists.expect_call('/foo/dir').and_return(False)
        subcommand.os.mkdir.expect_call('/foo/dir')

        (subcommand.os.path.exists.expect_call('/foo/dir/debug')
                .and_return(False))
        subcommand.os.mkdir.expect_call('/foo/dir/debug')

        cmd = subcommand.subcommand(func, (2, 3), subdir='dir')
        check_attributes(cmd, func, (2, 3), subdir='/foo/dir',
                         debug='/foo/dir/debug')
        self.god.check_playback()


    def _setup_fork_start_parent(self):
        self.god.stub_function(subcommand.os, 'fork')

        subcommand.os.fork.expect_call().and_return(1000)
        func = self.god.create_mock_function('func')
        cmd = _create_subcommand(func, [])
        cmd.fork_start()

        return cmd


    def test_fork_start_parent(self):
        cmd = self._setup_fork_start_parent()

        self.assertEquals(cmd.pid, 1000)
        self.god.check_playback()


    def _setup_fork_start_child(self):
        self.god.stub_function(subcommand.os, 'pipe')
        self.god.stub_function(subcommand.os, 'fork')
        self.god.stub_function(subcommand.os, 'close')
        self.god.stub_function(subcommand.os, 'write')
        self.god.stub_function(subcommand.cPickle, 'dumps')
        self.god.stub_function(subcommand.os, '_exit')


    def test_fork_start_child(self):
        self._setup_fork_start_child()

        func = self.god.create_mock_function('func')
        fork_hook = self.god.create_mock_function('fork_hook')
        join_hook = self.god.create_mock_function('join_hook')

        subcommand.subcommand.register_fork_hook(fork_hook)
        subcommand.subcommand.register_join_hook(join_hook)
        cmd = _create_subcommand(func, (1, 2))

        subcommand.os.pipe.expect_call().and_return((10, 20))
        subcommand.os.fork.expect_call().and_return(0)
        subcommand.os.close.expect_call(10)
        fork_hook.expect_call(cmd)
        func.expect_call(1, 2).and_return(True)
        subcommand.cPickle.dumps.expect_call(True,
                subcommand.cPickle.HIGHEST_PROTOCOL).and_return('True')
        subcommand.os.write.expect_call(20, 'True')
        subcommand.os.close.expect_call(20)
        join_hook.expect_call(cmd)
        subcommand.os._exit.expect_call(0)

        cmd.fork_start()
        self.god.check_playback()


    def test_fork_start_child_error(self):
        self._setup_fork_start_child()
        self.god.stub_function(subcommand.logging, 'exception')

        func = self.god.create_mock_function('func')
        cmd = _create_subcommand(func, (1, 2))
        error = Exception('some error')

        subcommand.os.pipe.expect_call().and_return((10, 20))
        subcommand.os.fork.expect_call().and_return(0)
        subcommand.os.close.expect_call(10)
        func.expect_call(1, 2).and_raises(error)
        subcommand.logging.exception.expect_call('function failed')
        subcommand.cPickle.dumps.expect_call(error,
                subcommand.cPickle.HIGHEST_PROTOCOL).and_return('error')
        subcommand.os.write.expect_call(20, 'error')
        subcommand.os.close.expect_call(20)
        subcommand.os._exit.expect_call(1)

        cmd.fork_start()
        self.god.check_playback()


    def _setup_poll(self):
        cmd = self._setup_fork_start_parent()
        self.god.stub_function(subcommand.os, 'waitpid')
        return cmd


    def test_poll_running(self):
        cmd = self._setup_poll()

        (subcommand.os.waitpid.expect_call(1000, subcommand.os.WNOHANG)
                .and_raises(subcommand.os.error('waitpid')))
        self.assertEquals(cmd.poll(), None)
        self.god.check_playback()


    def test_poll_finished_success(self):
        cmd = self._setup_poll()

        (subcommand.os.waitpid.expect_call(1000, subcommand.os.WNOHANG)
                .and_return((1000, 0)))
        self.assertEquals(cmd.poll(), 0)
        self.god.check_playback()


    def test_poll_finished_failure(self):
        cmd = self._setup_poll()
        self.god.stub_function(cmd, '_handle_exitstatus')

        (subcommand.os.waitpid.expect_call(1000, subcommand.os.WNOHANG)
                .and_return((1000, 10)))
        cmd._handle_exitstatus.expect_call(10).and_raises(Exception('fail'))

        self.assertRaises(Exception, cmd.poll)
        self.god.check_playback()


    def test_wait_success(self):
        cmd = self._setup_poll()

        (subcommand.os.waitpid.expect_call(1000, 0)
                .and_return((1000, 0)))

        self.assertEquals(cmd.wait(), 0)
        self.god.check_playback()


    def test_wait_failure(self):
        cmd = self._setup_poll()
        self.god.stub_function(cmd, '_handle_exitstatus')

        (subcommand.os.waitpid.expect_call(1000, 0)
                .and_return((1000, 10)))

        cmd._handle_exitstatus.expect_call(10).and_raises(Exception('fail'))
        self.assertRaises(Exception, cmd.wait)
        self.god.check_playback()


    def _setup_fork_waitfor(self):
        cmd = self._setup_fork_start_parent()
        self.god.stub_function(cmd, 'wait')
        self.god.stub_function(cmd, 'poll')
        self.god.stub_function(subcommand.time, 'time')
        self.god.stub_function(subcommand.time, 'sleep')
        self.god.stub_function(subcommand.utils, 'nuke_pid')

        return cmd


    def test_fork_waitfor_no_timeout(self):
        cmd = self._setup_fork_waitfor()

        cmd.wait.expect_call().and_return(0)

        self.assertEquals(cmd.fork_waitfor(), 0)
        self.god.check_playback()


    def test_fork_waitfor_success(self):
        cmd = self._setup_fork_waitfor()
        self.god.stub_function(cmd, 'wait')
        timeout = 10

        subcommand.time.time.expect_call().and_return(1)
        for i in xrange(timeout):
            subcommand.time.time.expect_call().and_return(i + 1)
            cmd.poll.expect_call().and_return(None)
            subcommand.time.sleep.expect_call(1)
        subcommand.time.time.expect_call().and_return(i + 2)
        cmd.poll.expect_call().and_return(0)

        self.assertEquals(cmd.fork_waitfor(timeout=timeout), 0)
        self.god.check_playback()


    def test_fork_waitfor_failure(self):
        cmd = self._setup_fork_waitfor()
        self.god.stub_function(cmd, 'wait')
        timeout = 10

        subcommand.time.time.expect_call().and_return(1)
        for i in xrange(timeout):
            subcommand.time.time.expect_call().and_return(i + 1)
            cmd.poll.expect_call().and_return(None)
            subcommand.time.sleep.expect_call(1)
        subcommand.time.time.expect_call().and_return(i + 3)
        subcommand.utils.nuke_pid.expect_call(cmd.pid)

        self.assertEquals(cmd.fork_waitfor(timeout=timeout), None)
        self.god.check_playback()


class parallel_test(unittest.TestCase):
    def setUp(self):
        self.god = mock.mock_god()
        self.god.stub_function(subcommand.cPickle, 'load')


    def tearDown(self):
        self.god.unstub_all()


    def _get_cmd(self, func, args):
        cmd = _create_subcommand(func, args)
        cmd.result_pickle = self.god.create_mock_class(file, 'file')
        return self.god.create_mock_class(cmd, 'subcommand')


    def _get_tasklist(self):
        return [self._get_cmd(lambda x: x * 2, (3,)),
                self._get_cmd(lambda: None, [])]


    def _setup_common(self):
        tasklist = self._get_tasklist()

        for task in tasklist:
            task.fork_start.expect_call()

        return tasklist


    def test_success(self):
        tasklist = self._setup_common()

        for task in tasklist:
            task.fork_waitfor.expect_call(timeout=None).and_return(0)
            (subcommand.cPickle.load.expect_call(task.result_pickle)
                    .and_return(6))
            task.result_pickle.close.expect_call()

        subcommand.parallel(tasklist)
        self.god.check_playback()


    def test_failure(self):
        tasklist = self._setup_common()

        for task in tasklist:
            task.fork_waitfor.expect_call(timeout=None).and_return(1)
            (subcommand.cPickle.load.expect_call(task.result_pickle)
                    .and_return(6))
            task.result_pickle.close.expect_call()

        self.assertRaises(subcommand.error.AutoservError, subcommand.parallel,
                          tasklist)
        self.god.check_playback()


    def test_timeout(self):
        self.god.stub_function(subcommand.time, 'time')

        tasklist = self._setup_common()
        timeout = 10

        subcommand.time.time.expect_call().and_return(1)

        for task in tasklist:
            subcommand.time.time.expect_call().and_return(1)
            task.fork_waitfor.expect_call(timeout=timeout).and_return(None)
            (subcommand.cPickle.load.expect_call(task.result_pickle)
                    .and_return(6))
            task.result_pickle.close.expect_call()

        self.assertRaises(subcommand.error.AutoservError, subcommand.parallel,
                          tasklist, timeout=timeout)
        self.god.check_playback()


    def test_return_results(self):
        tasklist = self._setup_common()

        tasklist[0].fork_waitfor.expect_call(timeout=None).and_return(0)
        (subcommand.cPickle.load.expect_call(tasklist[0].result_pickle)
                .and_return(6))
        tasklist[0].result_pickle.close.expect_call()

        error = Exception('fail')
        tasklist[1].fork_waitfor.expect_call(timeout=None).and_return(1)
        (subcommand.cPickle.load.expect_call(tasklist[1].result_pickle)
                .and_return(error))
        tasklist[1].result_pickle.close.expect_call()

        self.assertEquals(subcommand.parallel(tasklist, return_results=True),
                          [6, error])
        self.god.check_playback()


class test_parallel_simple(unittest.TestCase):
    def setUp(self):
        self.god = mock.mock_god()
        self.god.stub_function(subcommand, 'parallel')
        ctor = self.god.create_mock_function('subcommand')
        self.god.stub_with(subcommand, 'subcommand', ctor)


    def tearDown(self):
        self.god.unstub_all()


    def test_simple_success(self):
        func = self.god.create_mock_function('func')

        func.expect_call(3)

        subcommand.parallel_simple(func, (3,))
        self.god.check_playback()


    def test_simple_failure(self):
        func = self.god.create_mock_function('func')

        error = Exception('fail')
        func.expect_call(3).and_raises(error)

        self.assertRaises(Exception, subcommand.parallel_simple, func, (3,))
        self.god.check_playback()


    def test_simple_return_value(self):
        func = self.god.create_mock_function('func')

        result = 1000
        func.expect_call(3).and_return(result)

        self.assertEquals(subcommand.parallel_simple(func, (3,),
                                                     return_results=True),
                          [result])
        self.god.check_playback()


    def _setup_many(self, count, log):
        func = self.god.create_mock_function('func')

        args = []
        cmds = []
        for i in xrange(count):
            arg = i + 1
            args.append(arg)

            if log:
                subdir = str(arg)
            else:
                subdir = None

            cmd = object()
            cmds.append(cmd)

            (subcommand.subcommand.expect_call(func, [arg], subdir)
                    .and_return(cmd))

        subcommand.parallel.expect_call(cmds, None, return_results=False)
        return func, args


    def test_passthrough(self):
        func, args = self._setup_many(4, True)

        subcommand.parallel_simple(func, args)
        self.god.check_playback()


    def test_nolog(self):
        func, args = self._setup_many(3, False)

        subcommand.parallel_simple(func, args, log=False)
        self.god.check_playback()


if __name__ == '__main__':
    unittest.main()
