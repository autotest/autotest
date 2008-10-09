#!/usr/bin/python

__author__ = "raphtee@google.com (Travis Miller)"

import unittest, os, tempfile
import common
from autotest_lib.server import autotest, utils, hosts, server_job
from autotest_lib.client.common_lib import utils as client_utils, packages
from autotest_lib.client.common_lib.test_utils import mock


class TestBaseAutotest(unittest.TestCase):
    def setUp(self):
        # create god
        self.god = mock.mock_god()

        # create mock host object
        self.host = self.god.create_mock_class(hosts.RemoteHost, "host")
        self.host.hostname = "hostname"
        self.host.job = self.god.create_mock_class(server_job.server_job,
                                                   "job")
        self.host.job.run_test_cleanup = True

        # stubs
        self.god.stub_function(utils, "get_server_dir")
        self.god.stub_function(utils, "run")
        self.god.stub_function(utils, "get")
        self.god.stub_function(utils, "read_keyval")
        self.god.stub_function(utils, "write_keyval")
        self.god.stub_function(tempfile, "mkstemp")
        self.god.stub_function(tempfile, "mktemp")
        self.god.stub_function(os, "getcwd")
        self.god.stub_function(os, "system")
        self.god.stub_function(os, "chdir")
        self.god.stub_function(os, "makedirs")
        self.god.stub_function(os, "remove")
        self.god.stub_function(os.path, "exists")
        self.god.stub_function(utils, "sh_escape")
        self.god.stub_function(autotest, "open")
        self.god.stub_function(autotest.global_config.global_config,
                               "get_config_value")
        self.god.stub_class(autotest, "_Run")
        self.god.stub_class(server_job, "log_collector")


    def tearDown(self):
       self.god.unstub_all()


    def construct(self):
        # setup
        self.serverdir = "serverdir"

        # record
        utils.get_server_dir.expect_call().and_return(self.serverdir)

        # create the autotest object
        self.base_autotest = autotest.BaseAutotest(self.host)

        # stub out abspath
        self.god.stub_function(os.path, "abspath")

        # check
        self.god.check_playback()


    def test_constructor(self):
        self.construct()

        # we should check the calls
        self.god.check_playback()


    def test_install(self):
        self.construct()

        # setup
        self.god.stub_class(packages, "PackageManager")
        self.base_autotest.got = False
        location = os.path.join(self.serverdir, '../client')
        location = os.path.abspath.expect_call(location).and_return(location)

        # record
        os.getcwd.expect_call().and_return('cwd')
        os.chdir.expect_call(os.path.join(self.serverdir, '../client'))
        os.system.expect_call('tools/make_clean')
        os.chdir.expect_call('cwd')
        utils.get.expect_call(os.path.join(self.serverdir,
            '../client')).and_return('source_material')

        self.host.wait_up.expect_call(timeout=30)
        self.host.setup.expect_call()
        self.host.get_autodir.expect_call().and_return("autodir")
        self.host.set_autodir.expect_call("autodir")
        utils.sh_escape.expect_call("autodir").and_return("autodir")
        self.host.run.expect_call('mkdir -p "autodir"')
        c = autotest.global_config.global_config
        c.get_config_value.expect_call("PACKAGES",
            'fetch_location', type=list).and_return('repos')
        pkgmgr = packages.PackageManager.expect_new('autodir',
            repo_urls='repos', do_locking=False, run_function=self.host.run,
            run_function_dargs=dict(timeout=600))
        pkg_dir = os.path.join('autodir', 'packages')
        cmd = ('cd autodir && ls | grep -v "^packages$"'
               ' | xargs rm -rf && rm -rf .[^.]*')
        self.host.run.expect_call(cmd)
        pkgmgr.install_pkg.expect_call('autotest', 'client', pkg_dir,
                                       'autodir', preserve_install_dir=True)

        # run and check
        self.base_autotest.install()
        self.god.check_playback()


    def test_run(self):
        self.construct()

        # setup
        control = "control"

        # stub out install
        self.god.stub_function(self.base_autotest, "install")

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

        utils.get.expect_call(control).and_return("temp")

        cfile = self.god.create_mock_class(file, "file")
        autotest.open.expect_call("temp", 'r').and_return(cfile)
        cfile_orig = "original control file"
        cfile.read.expect_call().and_return(cfile_orig)
        cfile.close.expect_call()
        c = autotest.global_config.global_config
        c.get_config_value.expect_call("PACKAGES",
            'fetch_location', type=list).and_return('repos')
        control_file_new = []
        control_file_new.append('job.add_repository(repos)\n')
        control_file_new.append(cfile_orig)
        autotest.open.expect_call("temp", 'w').and_return(cfile)
        cfile.write.expect_call('\n'.join(control_file_new))
        cfile.close.expect_call()

        self.host.send_file.expect_call("temp", run_obj.remote_control_file)
        os.path.abspath.expect_call('temp').and_return('control_file')
        os.path.abspath.expect_call('autodir/control.None.state').and_return(
            'autodir/control.None.state')
        os.remove.expect_call("temp")
        run_obj.execute_control.expect_call(timeout=30)
        collector = server_job.log_collector.expect_new(self.host, tag, '.')
        collector.collect_client_job_results.expect_call()

        autotest.open.expect_call('./control.None.autoserv.state').and_raises(
            Exception("File not found"))
        os.remove.expect_call('./control.None.autoserv.state').and_raises(
            Exception("File not found"))

        # run and check output
        self.base_autotest.run(control, timeout=30)
        self.god.check_playback()


if __name__ == "__main__":
    unittest.main()
