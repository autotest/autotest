#!/usr/bin/python

__author__ = "raphtee@google.com (Travis Miller)"

import unittest, os, tempfile, logging
import common
from autotest_lib.server import autotest, utils, hosts, server_job, profilers
from autotest_lib.client.bin import sysinfo
from autotest_lib.client.common_lib import utils as client_utils, packages
from autotest_lib.client.common_lib import error
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
        self.host.job.last_boot_tag = 'Autotest'
        self.host.job.sysinfo = self.god.create_mock_class(
            sysinfo.sysinfo, "sysinfo")
        self.host.job.profilers = self.god.create_mock_class(
            profilers.profilers, "profilers")
        self.host.job.profilers.add_log = {}
        self.host.job.tmpdir = "/job/tmp"
        self.host.job.default_profile_only = False

        # stubs
        self.god.stub_function(utils, "get_server_dir")
        self.god.stub_function(utils, "run")
        self.god.stub_function(utils, "get")
        self.god.stub_function(utils, "read_keyval")
        self.god.stub_function(utils, "write_keyval")
        self.god.stub_function(utils, "system")
        self.god.stub_function(tempfile, "mkstemp")
        self.god.stub_function(tempfile, "mktemp")
        self.god.stub_function(os, "getcwd")
        self.god.stub_function(os, "system")
        self.god.stub_function(os, "chdir")
        self.god.stub_function(os, "makedirs")
        self.god.stub_function(os, "remove")
        self.god.stub_function(os, "fdopen")
        self.god.stub_function(os.path, "exists")
        self.god.stub_function(os.path, "isdir")
        self.god.stub_function(autotest, "open")
        self.god.stub_function(autotest.global_config.global_config,
                               "get_config_value")
        self.god.stub_function(logging, "exception")
        self.god.stub_class(autotest, "_Run")
        self.god.stub_class(autotest, "log_collector")


    def tearDown(self):
        self.god.unstub_all()


    def construct(self):
        # setup
        self.serverdir = "serverdir"

        # record
        utils.get_server_dir.expect_call().and_return(self.serverdir)

        # create the autotest object
        self.base_autotest = autotest.BaseAutotest(self.host)
        self.god.stub_function(self.base_autotest, "_install_using_send_file")

        # stub out abspath
        self.god.stub_function(os.path, "abspath")

        # check
        self.god.check_playback()


    def record_install_prologue(self):
        self.construct()

        # setup
        self.god.stub_class(packages, "PackageManager")
        self.base_autotest.got = False
        location = os.path.join(self.serverdir, '../client')
        location = os.path.abspath.expect_call(location).and_return(location)

        # record
        os.getcwd.expect_call().and_return('cwd')
        os.chdir.expect_call(os.path.join(self.serverdir, '../client'))
        utils.system.expect_call('tools/make_clean', ignore_status=True)
        os.chdir.expect_call('cwd')
        utils.get.expect_call(os.path.join(self.serverdir,
            '../client')).and_return('source_material')

        self.host.wait_up.expect_call(timeout=30)
        self.host.setup.expect_call()
        self.host.get_autodir.expect_call().and_return("autodir")
        self.host.set_autodir.expect_call("autodir")
        self.host.run.expect_call('mkdir -p autodir')
        self.host.run.expect_call('rm -rf autodir/results/*',
                                  ignore_status=True)


    def test_constructor(self):
        self.construct()

        # we should check the calls
        self.god.check_playback()


    def test_full_client_install(self):
        self.record_install_prologue()

        os.path.isdir.expect_call('source_material').and_return(True)
        c = autotest.global_config.global_config
        c.get_config_value.expect_call('PACKAGES',
                                       'serve_packages_from_autoserv',
                                       type=bool).and_return(False)
        self.host.send_file.expect_call('source_material', 'autodir',
                                        delete_dest=True)

        # run and check
        self.base_autotest.install_full_client()
        self.god.check_playback()


    def test_autoserv_install(self):
        self.record_install_prologue()

        c = autotest.global_config.global_config
        c.get_config_value.expect_call('PACKAGES',
            'fetch_location', type=list, default=[]).and_return([])

        os.path.isdir.expect_call('source_material').and_return(True)
        c.get_config_value.expect_call('PACKAGES',
                                       'serve_packages_from_autoserv',
                                       type=bool).and_return(True)
        self.base_autotest._install_using_send_file.expect_call(self.host,
                                                                'autodir')

        # run and check
        self.base_autotest.install()
        self.god.check_playback()


    def test_packaging_install(self):
        self.record_install_prologue()

        c = autotest.global_config.global_config
        c.get_config_value.expect_call('PACKAGES',
            'fetch_location', type=list, default=[]).and_return(['repo'])
        pkgmgr = packages.PackageManager.expect_new('autodir',
            repo_urls=['repo'], hostname='hostname', do_locking=False,
            run_function=self.host.run, run_function_dargs=dict(timeout=600))
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
        self.god.stub_class(packages, "PackageManager")

        # record
        self.base_autotest.install.expect_call(self.host)
        self.host.wait_up.expect_call(timeout=30)
        os.path.abspath.expect_call('.').and_return('.')
        run_obj = autotest._Run.expect_new(self.host, '.', None, False, False)
        tag = None
        run_obj.manual_control_file = os.path.join('autodir',
                                                   'control.%s' % tag)
        run_obj.remote_control_file = os.path.join('autodir',
                                                   'control.%s.autoserv' % tag)
        run_obj.tag = tag
        run_obj.autodir = 'autodir'
        run_obj.verify_machine.expect_call()
        run_obj.verify_machine.expect_call()
        run_obj.background = False
        debug = os.path.join('.', 'debug')
        os.makedirs.expect_call(debug)
        delete_file_list = [run_obj.remote_control_file,
                            run_obj.remote_control_file + '.state',
                            run_obj.manual_control_file,
                            run_obj.manual_control_file + '.state']
        cmd = ';'.join('rm -f ' + control for control in delete_file_list)
        self.host.run.expect_call(cmd, ignore_status=True)

        utils.get.expect_call(control).and_return("temp")

        c = autotest.global_config.global_config
        c.get_config_value.expect_call("PACKAGES",
            'fetch_location', type=list).and_return(['repo'])
        pkgmgr = packages.PackageManager.expect_new('autotest',
                                                     repo_urls=['repo'],
                                                     hostname='hostname')

        cfile = self.god.create_mock_class(file, "file")
        cfile_orig = "original control file"
        cfile_new = "job.add_repository(['repo'])\n"
        cfile_new += cfile_orig

        autotest.open.expect_call("temp").and_return(cfile)
        cfile.read.expect_call().and_return(cfile_orig)
        autotest.open.expect_call("temp", 'w').and_return(cfile)
        cfile.write.expect_call(cfile_new)

        def _expect_create_aux_file(directory):
            tempfile.mkstemp.expect_call(dir=directory).and_return(
                    (5, os.path.join(directory, "file1")))
            mock_temp = self.god.create_mock_class(file, "file1")
            mock_temp.write = lambda s: None
            mock_temp.close = lambda: None
            os.fdopen.expect_call(5, "w").and_return(mock_temp)

        run_obj.config_file = 'my_config'
        _expect_create_aux_file("/job/tmp")
        self.host.send_file.expect_call("/job/tmp/file1",
                                        "my_config")
        os.remove.expect_call("/job/tmp/file1")

        self.host.job.preprocess_client_state.expect_call().and_return(
            '/job/tmp/file1')
        self.host.send_file.expect_call(
            "/job/tmp/file1", "autodir/control.None.autoserv.init.state")
        os.remove.expect_call("/job/tmp/file1")

        self.host.send_file.expect_call("temp", run_obj.remote_control_file)
        os.path.abspath.expect_call('temp').and_return('control_file')
        os.path.abspath.expect_call('control').and_return('control')
        os.remove.expect_call("temp")

        run_obj.execute_control.expect_call(timeout=30,
                                            client_disconnect_timeout=1800)

        # run and check output
        self.base_autotest.run(control, timeout=30)
        self.god.check_playback()


    def _stub_get_client_autodir_paths(self):
        def mock_get_client_autodir_paths(cls, host):
            return ['/some/path', '/another/path']
        self.god.stub_with(autotest.Autotest, 'get_client_autodir_paths',
                           classmethod(mock_get_client_autodir_paths))


    def _expect_failed_run(self, command):
        (self.host.run.expect_call(command)
         .and_raises(error.AutoservRunError('dummy', object())))


    def test_get_installed_autodir(self):
        self._stub_get_client_autodir_paths()
        self.host.get_autodir.expect_call().and_return(None)
        self._expect_failed_run('test -x /some/path/bin/autotest')
        self.host.run.expect_call('test -x /another/path/bin/autotest')

        autodir = autotest.Autotest.get_installed_autodir(self.host)
        self.assertEquals(autodir, '/another/path')


    def test_get_install_dir(self):
        self._stub_get_client_autodir_paths()
        self.host.get_autodir.expect_call().and_return(None)
        self._expect_failed_run('test -x /some/path/bin/autotest')
        self._expect_failed_run('test -x /another/path/bin/autotest')
        self._expect_failed_run('mkdir -p /some/path')
        self.host.run.expect_call('mkdir -p /another/path')

        install_dir = autotest.Autotest.get_install_dir(self.host)
        self.assertEquals(install_dir, '/another/path')


    def test_client_logger_process_line_log_copy_collection_failure(self):
        collector = autotest.log_collector.expect_new(self.host, '', '')
        logger = autotest.client_logger(self.host, '', '')
        collector.collect_client_job_results.expect_call().and_raises(
                Exception('log copy failure'))
        logging.exception.expect_call(mock.is_string_comparator())
        logger._process_line('AUTOTEST_TEST_COMPLETE:/autotest/fifo1')


    def test_client_logger_process_line_log_copy_fifo_failure(self):
        collector = autotest.log_collector.expect_new(self.host, '', '')
        logger = autotest.client_logger(self.host, '', '')
        collector.collect_client_job_results.expect_call()
        self.host.run.expect_call('echo A > /autotest/fifo2').and_raises(
                Exception('fifo failure'))
        logging.exception.expect_call(mock.is_string_comparator())
        logger._process_line('AUTOTEST_TEST_COMPLETE:/autotest/fifo2')


    def test_client_logger_process_line_package_install_fifo_failure(self):
        collector = autotest.log_collector.expect_new(self.host, '', '')
        logger = autotest.client_logger(self.host, '', '')
        self.god.stub_function(logger, '_send_tarball')

        c = autotest.global_config.global_config
        c.get_config_value.expect_call('PACKAGES',
                                       'serve_packages_from_autoserv',
                                       type=bool).and_return(True)
        logger._send_tarball.expect_call('pkgname.tar.bz2', '/autotest/dest/')
        
        self.host.run.expect_call('echo B > /autotest/fifo3').and_raises(
                Exception('fifo failure'))
        logging.exception.expect_call(mock.is_string_comparator())
        logger._process_line('AUTOTEST_FETCH_PACKAGE:pkgname.tar.bz2:'
                             '/autotest/dest/:/autotest/fifo3')


    def test_client_logger_write_handles_process_line_failures(self):
        collector = autotest.log_collector.expect_new(self.host, '', '')
        logger = autotest.client_logger(self.host, '', '')
        logger.server_warnings = [(x, 'warn%d' % x) for x in xrange(5)]
        self.god.stub_function(logger, '_process_warnings')
        self.god.stub_function(logger, '_process_line')
        def _update_timestamp(line):
            logger.newest_timestamp += 2
        class ProcessingException(Exception):
            pass
        def _read_warnings():
            return [(5, 'warn5')]
        logger._update_timestamp = _update_timestamp
        logger.newest_timestamp = 0
        self.host.job._read_warnings = _read_warnings
        # process line1, newest_timestamp -> 2
        logger._process_warnings.expect_call(
                '', {}, [(0, 'warn0'), (1, 'warn1')])
        logger._process_line.expect_call('line1')
        # process line2, newest_timestamp -> 4, failure occurs during process
        logger._process_warnings.expect_call(
                '', {}, [(2, 'warn2'), (3, 'warn3')])
        logger._process_line.expect_call('line2').and_raises(
                ProcessingException('line processing failure'))
        # when we call write with data we should get an exception
        self.assertRaises(ProcessingException, logger.write,
                          'line1\nline2\nline3\nline4')
        # but, after the exception, the server_warnings and leftover buffers
        # should contain the unprocessed data, and ONLY the unprocessed data
        self.assertEqual(logger.server_warnings, [(4, 'warn4'), (5, 'warn5')])
        self.assertEqual(logger.leftover, 'line2\nline3\nline4')


if __name__ == "__main__":
    unittest.main()
