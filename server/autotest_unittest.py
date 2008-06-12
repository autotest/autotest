#!/usr/bin/python

__author__ = "raphtee@google.com (Travis Miller)"

import os, unittest, tempfile
import common
from autotest_lib.server import autotest
from autotest_lib.server.hosts import ssh_host
from autotest_lib.client.common_lib import utils as client_utils
from autotest_lib.client.common_lib.test_utils import mock
import pdb

class TestBaseAutotest(unittest.TestCase):
    def setUp(self):
        # create god
        self.god = mock.mock_god()

        # create mock host object
        self.host = self.god.create_mock_class(ssh_host.SSHHost, "host")
        self.host.hostname = "hostname"

        # stubs
        self.god.stub_function(autotest.utils, "get_server_dir")
        self.god.stub_function(autotest.utils, "run")
        self.god.stub_function(autotest.utils, "get")
        self.god.stub_function(autotest.utils, "read_keyval")
        self.god.stub_function(autotest.utils, "write_keyval")
        self.god.stub_function(tempfile, "mkstemp")
        self.god.stub_function(tempfile, "mktemp")
        self.god.stub_function(os, "getcwd")
        self.god.stub_function(os, "system")
        self.god.stub_function(os, "chdir")
        self.god.stub_function(os, "makedirs")
        self.god.stub_function(os, "remove")
        self.god.stub_function(os.path, "abspath")
        self.god.stub_function(os.path, "exists")
        self.god.stub_class(autotest, "_Run")


    def tearDown(self):
       self.god.unstub_all()


    def construct(self):
        # setup
        self.serverdir = "serverdir"

        # record
        autotest.utils.get_server_dir.expect_call().and_return(self.serverdir)

        # create the autotest object
        self.base_autotest = autotest.BaseAutotest(self.host)

        # check
        self.god.check_playback()


    def test_constructor(self):
        self.construct()

        # we should check the calls
        self.god.check_playback()


    def test_install(self):
        self.construct()

        # setup
        self.source_material = None

        # record
        location = os.path.join(self.serverdir, '../client')
        os.path.abspath.expect_call(location).and_return(location)
        os.getcwd.expect_call().and_return("current/working/dir")
        os.chdir.expect_call(location)
        os.system.expect_call('tools/make_clean')
        os.chdir.expect_call("current/working/dir")
        autotest.utils.get.expect_call(location)
        self.host.wait_up.expect_call(timeout=30)
        self.host.setup.expect_call()
        self.host.get_autodir.expect_call().and_return("autodir")
        self.host.run.expect_call('mkdir -p "autodir"')
        if getattr(self.host, 'site_install_autotest', None):
            self.host.site_install_autotest.expect_call().and_return(True)
        else:
            cmd_result = client_utils.CmdResult()
            autotest.utils.run.expect_call('which svn').and_return(cmd_result)
            self.host.run('svn checkout %s autodir' % (autotest.AUTOTEST_SVN))

        self.base_autotest.install()
        self.god.check_playback()


    def test_run(self):
        self.construct()

        # setup
        control = "control"

        # stub out install
        self.god.stub_function(self.base_autotest, "install")
        self.god.stub_function(self.base_autotest, "prepare_for_copying_logs")
        self.god.stub_function(self.base_autotest, "process_copied_logs")
        self.god.stub_function(self.base_autotest, "postprocess_copied_logs")

        # record
        self.base_autotest.install.expect_call(self.host)
        self.host.wait_up.expect_call(timeout=30)
        os.path.abspath.expect_call('.').and_return('.')
        run_obj = autotest._Run.expect_new(self.host, '.', None, False)
        tag = None
        run_obj.manual_control_file = os.path.join('autodir',
                                                   'control.%s' % tag)
        run_obj.remote_control_file = os.path.join('autodir',
                                                   'control.%s.autoserv' % tag)
        run_obj.tag = tag
        run_obj.autodir = 'autodir'
        run_obj.verify_machine.expect_call()
        run_obj.verify_machine.expect_call()
        debug = os.path.join('.', 'debug')
        os.makedirs.expect_call(debug)
        for control in [run_obj.remote_control_file,
                        run_obj.remote_control_file + '.state',
                        run_obj.manual_control_file,
                        run_obj.manual_control_file + '.state']:
            self.host.run.expect_call('rm -f ' + control)

        autotest.utils.get.expect_call(control).and_return("temp")
        self.host.send_file.expect_call("temp", run_obj.remote_control_file)
        os.path.abspath.expect_call("temp").and_return("temp")
        os.path.abspath.expect_call(control).and_return(control)
        os.remove.expect_call("temp")

        run_obj.execute_control.expect_call(timeout=None)
        self.host.wait_up.expect_call(timeout=30)
        results = os.path.join("autodir", 'results', 'default')
        self.base_autotest.prepare_for_copying_logs.expect_call(results, '.',
            self.host).and_return("keyval_path")
        self.host.get_file.expect_call(results + '/', '.')
        self.base_autotest.process_copied_logs.expect_call('.', self.host,
                                                           "keyval_path")
        self.base_autotest.postprocess_copied_logs.expect_call(results,
                                                               self.host)

        # run and check output
        self.base_autotest.run(control)
        self.god.check_playback()

    def test_prepare_for_copying_logs(self):
        self.construct()

        # record
        src = "src"
        dest = "dest"
        keyval_path = ''
        os.path.exists.expect_call(os.path.join(dest,
                                                'keyval')).and_return(True)
        tempfile.mkstemp.expect_call(
            '.keyval_%s' % self.host.hostname).and_return((None, keyval_path))
        self.host.get_file.expect_call(os.path.join(src, 'keyval'), keyval_path)
        tempfile.mktemp.expect_call().and_return("temp_keyval")
        self.host.run.expect_call('mv %s temp_keyval' %
                                   os.path.join(src, 'keyval'))

        # run and check
        self.base_autotest.prepare_for_copying_logs(src, dest, self.host)
        self.god.check_playback()


    def test_process_copied_logs(self):
        self.construct()

        # record
        dest = "dest"
        keyval_path = "keyval_path"
        os.path.exists.expect_call(os.path.join(dest,
                                                'keyval')).and_return(True)
        old_keyval = {"version": 1, "author": "me"}
        new_keyval = {"version": 1, "data": "foo"}
        autotest.utils.read_keyval.expect_call(
            keyval_path).and_return(new_keyval)
        autotest.utils.read_keyval.expect_call(dest).and_return(old_keyval)
        tmp_keyval = {}
        for key, val in new_keyval.iteritems():
            if key not in old_keyval:
                tmp_keyval[key] = val
        autotest.utils.write_keyval.expect_call(dest, tmp_keyval)
        os.remove.expect_call(keyval_path)

        # run check
        self.base_autotest.process_copied_logs(dest, self.host, keyval_path)
        self.god.check_playback()


if __name__ == "__main__":
    unittest.main()
