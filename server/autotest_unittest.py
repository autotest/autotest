#!/usr/bin/python2.4

__author__ = "raphtee@google.com (Travis Miller)"

import os, unittest
import common
from autotest_lib.server import autotest, utils
from autotest_lib.client.common_lib import utils as client_utils
from autotest_lib.server.hosts import ssh_host
from autotest_lib.client.common_lib.test_utils import mock


class TestBaseAutotest(unittest.TestCase):
    def setUp(self):
        # create god
        self.god = mock.mock_god()

        # stub out utils
        self.utils_obj = self.god.create_mock_class(utils, "utils")
        self.old_utils = autotest.utils
        autotest.utils = self.utils_obj

        # stub out os
        self.old_os = autotest.os
        self.os_obj = self.god.create_mock_class(os, "os")
        autotest.os = self.os_obj

        # stub out os.path
        self.path_obj = self.god.create_mock_class(os.path, "os.path")
        autotest.os.path = self.path_obj

        # need to set return of one function in utils called in constr.
        self.server_dir = "autotest_lib.server"
        func_call = self.utils_obj.get_server_dir.expect_call()
        func_call.and_return(self.server_dir)

        # create our host mock (and give it a hostname)
        self.host = self.god.create_mock_class(ssh_host.SSHHost,
                                               "SSHHost")
        self.host.hostname = "foo"

        # create the autotest object
        self.base_autotest = autotest.BaseAutotest(self.host)


    def tearDown(self):
        # put things back
        autotest.utils = self.old_utils
        autotest.os = self.old_os


    def test_constructor(self):
        # we should check the calls
        self.god.check_playback()

    def common_install_test_setup(self, autodir, is_site_install_autotest):
        # mock other methods
        old_get_autodir = autotest._get_autodir
        get_autodir_obj = self.god.create_mock_function("_get_autodir")
        autotest._get_autodir = get_autodir_obj

        self.base_autotest.got = True
        self.source_material = None

        # record calls
        self.host.wait_up.expect_call(timeout=30)
        self.host.setup.expect_call()
        get_autodir_obj.expect_call(self.host).and_return(autodir)
        rt = self.utils_obj.sh_escape.expect_call(autodir)
        rt.and_return(autodir)
        self.host.run.expect_call('mkdir -p "%s"' % (autodir))
        rt = self.host.site_install_autotest.expect_call()
        rt.and_return(is_site_install_autotest)

        return old_get_autodir


    def common_install_test_teardown(self, old_get_autodir):
        # put things back
        autotest._get_autodir = old_get_autodir


    def test_install1(self):
        # setup
        autodir = "autodir"
        old_get_autodir = self.common_install_test_setup(autodir, True)

        # run test
        self.base_autotest.install()

        # check
        self.assertTrue(self.base_autotest.installed)
        self.god.check_playback()

        # put back
        self.common_install_test_teardown(old_get_autodir)


    def test_install2(self):
        # setup
        autodir = "autodir"
        old_get_autodir = self.common_install_test_setup(autodir, False)
        cmd = 'which svn'
        cmdresult = client_utils.CmdResult(cmd)
        self.utils_obj.run.expect_call(cmd).and_return(cmdresult)
        cmd = 'svn checkout %s %s' % (autotest.AUTOTEST_SVN, autodir)
        self.host.run.expect_call(cmd)

        # run test
        self.base_autotest.install()

        # check
        self.assertTrue(self.base_autotest.installed)
        self.god.check_playback()

        # put back
        self.common_install_test_teardown(old_get_autodir)


    def test_get(self):
        # setup
        location = "autotest_lib.client"
        cwd = "current_dir"
        self.os_obj.getcwd.expect_call().and_return(cwd)
        self.os_obj.chdir.expect_call(location)
        self.os_obj.system.expect_call('tools/make_clean')
        self.os_obj.chdir.expect_call(cwd)

        # call method under test
        self.base_autotest.get(location)

        # do tests
        self.assertTrue(self.base_autotest.got)
        self.god.check_playback()


    def test_get_default(self):
        # setup the test
        location = "autotest_lib.client"
        self.path_obj.join.expect_call(self.base_autotest.serverdir,
                                       '../client').and_return(location)
        self.path_obj.abspath.expect_call(location).and_return(location)
        cwd = "current_dir"
        self.os_obj.getcwd.expect_call().and_return(cwd)
        self.os_obj.chdir.expect_call(location)
        self.os_obj.system.expect_call('tools/make_clean')
        self.os_obj.chdir.expect_call(cwd)

        # call method under test
        self.base_autotest.get()

        # do tests
        self.assertTrue(self.base_autotest.got)
        self.god.check_playback()


    def test_run_default(self):
        # need to stub out _get_host_and_setup
        old_func = self.base_autotest._get_host_and_setup
        name = "_get_host_and_setup"
        new_func = self.god.create_mock_function(name)
        self.base_autotest._get_host_and_setup = new_func

        # need to stub out _do_run
        old_do_run = self.base_autotest._do_run
        do_run = self.god.create_mock_function("_do_run")
        self.base_autotest._do_run = do_run

        # need a mock of _Run object
        run = self.god.create_mock_class(autotest._Run, "run")

        # need a mock for _Run constuctor
        oldRun = autotest._Run
        newRun = self.god.create_mock_function("_Run")
        autotest._Run = newRun

        new_func.expect_call(None).and_return(self.host)
        results_dir = "results_dir"
        self.path_obj.abspath.expect_call(".").and_return(results_dir)
        newRun.expect_call(self.host,
                           results_dir, None, False).and_return(run)
        do_run.expect_call("control", results_dir, self.host, run, None)

        # call method
        self.base_autotest.run("control")

        # do test
        self.god.check_playback()

        # put things back
        self.base_autotest._get_host_and_setup = old_func
        self.base_autotest._do_run = old_do_run
        autotest._Run = oldRun


    def test_prepare_for_copying_logs1(self):
        src = "src"
        dest = "dest"
        keyval_path = ''
        dkeyval = "dest/keyval"

        # setup
        self.path_obj.join.expect_call(dest,
                                       'keyval').and_return(dkeyval)
        self.path_obj.exists.expect_call(dkeyval).and_return(False)

        # run test
        self.base_autotest.prepare_for_copying_logs(src, dest,
                                                    self.host)

        # check
        self.god.check_playback()


    def test_prepare_for_copying_logs2(self):
        src = "src"
        dest = "dest"
        keyval_path = ''
        dkeyval = "dest/keyval"
        skeyval = "src/keyval"
        file_path = (0, ".keyavl_host")

        # make stub for tempfile.mkstemp
        old_mkstemp = autotest.tempfile.mkstemp
        mkstemp_obj = self.god.create_mock_function("tempfile.mkstemp")
        autotest.tempfile.mkstemp = mkstemp_obj

        # setup
        self.path_obj.join.expect_call(dest,
                                       'keyval').and_return(dkeyval)
        self.path_obj.exists.expect_call(dkeyval).and_return(True)
        mkstemp_obj.expect_call('.keyval_%s'
                             % self.host.hostname).and_return(file_path)
        self.path_obj.join.expect_call(src,
                                       'keyval').and_return(skeyval)
        self.host.get_file.expect_call(skeyval, file_path[1])
        self.path_obj.join.expect_call(src,
                                       'keyval').and_return(skeyval)
        self.host.run.expect_call('rm -rf %s' % (skeyval))

        # run test
        self.base_autotest.prepare_for_copying_logs(src, dest,
                                                    self.host)

        # check results
        self.god.check_playback()

        # set things back
        autotest.tempfile.mkstemp = old_mkstemp


    def test_process_copied_logs_no_dest_keyval(self):
        # setup test
        dest = "dest"
        path = "keyval_path"
        self.path_obj.join.expect_call(dest, 'keyval').and_return(path)
        self.path_obj.exists.expect_call(path).and_return(False)

        # run test
        self.base_autotest.process_copied_logs(dest, self.host, path)

        # run check
        self.god.check_playback()


    def test_process_copied_logs_with_dest_keyval(self):
        # setup test
        dest = "dest"
        kpath = "keyval_path"
        path = "path"
        self.path_obj.join.expect_call(dest, 'keyval').and_return(path)
        self.path_obj.exists.expect_call(path).and_return(True)

        vals = {'version': 1, 'author': "wonder woman"}
        kvals = {'version': 1}
        mvals = {'author': "wonder woman"}

        self.utils_obj.read_keyval.expect_call(path).and_return(vals)
        self.path_obj.join.expect_call(dest, 'keyval').and_return(kpath)
        self.utils_obj.read_keyval.expect_call(kpath).and_return(kvals)
        self.path_obj.join.expect_call(dest, 'keyval').and_return(dest)
        self.utils_obj.write_keyval.expect_call(dest, mvals)
        self.os_obj.remove.expect_call(path)

        # call test
        self.base_autotest.process_copied_logs(dest, self.host, path)

        # run check
        self.god.check_playback()


    def test_run_timed_test(self):
        pass


if __name__ == "__main__":
    unittest.main()
