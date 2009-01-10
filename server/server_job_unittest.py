#!/usr/bin/python

import unittest, os, shutil, stat, sys, time, tempfile, warnings
import common
from autotest_lib.server import server_job, test, subcommand, hosts, autotest
from autotest_lib.client.bin import sysinfo
from autotest_lib.client.common_lib import utils, error, host_protections
from autotest_lib.client.common_lib import packages
from autotest_lib.tko import db as tko_db, status_lib, utils as tko_utils
from autotest_lib.client.common_lib.test_utils import mock
from autotest_lib.tko.parsers import version_1 as parser_mod
from autotest_lib.tko.parsers import version_0 as parser_mod0


class CopyLogsTest(unittest.TestCase):
    def setUp(self):
        self.control = "control"
        self.args = ""
        self.resultdir = "results"
        self.label = "default"
        self.user = "user"
        self.machines = ('abcd1', 'abcd2', 'abcd3')

        # make god
        self.god = mock.mock_god()

        # stub out some common functions
        self.god.stub_function(os.path, 'exists')
        self.god.stub_function(os, 'mkdir')
        self.god.stub_function(os, 'access')
        self.god.stub_function(os, 'makedirs')
        self.god.stub_function(os.path, 'isdir')
        self.god.stub_function(os, 'chmod')
        self.god.stub_function(os, 'chdir')
        self.god.stub_function(os, 'unlink')
        self.god.stub_function(server_job, 'get_site_job_data')
        self.god.stub_function(server_job, 'open')
        self.god.stub_function(utils, 'write_keyval')

        self.construct_server_job()


    def tearDown(self):
        self.god.unstub_all()


    def construct_server_job(self):
        # XXX(gps): These expect_call's must be kept in perfect sync
        # call for call with what base_server_job does.  This is too
        # painful to maintain.

        # setup recording for constructor
        file_obj = self.god.create_mock_class(file, "file")
        server_job.open.expect_call(self.control, 'r').and_return(file_obj)
        file_obj.read.expect_call().and_return('')
        os.path.exists.expect_call(
                mock.is_string_comparator()).and_return(False)
        os.mkdir.expect_call(mock.is_string_comparator())
        os.path.exists.expect_call(
                mock.is_string_comparator()).and_return(False)
        os.mkdir.expect_call(mock.is_string_comparator())

        self.god.mock_up(sysinfo, 'sysinfo')
        sysinfo.sysinfo.expect_call(mock.is_string_comparator())

        os.access.expect_call(mock.is_string_comparator(),
                              os.W_OK).and_return(False)
        os.makedirs.expect_call(mock.is_string_comparator(), 0700)

        os.access.expect_call(mock.is_string_comparator(),
                              os.W_OK).and_return(True)
        os.path.isdir.expect_call(mock.is_string_comparator()).and_return(False)
        self.god.stub_function(tempfile, 'gettempdir')
        tempfile.gettempdir.expect_call().and_return('/tmp/server_job_unittest')
        os.makedirs.expect_call(mock.is_string_comparator(),
                                0700).and_raises(os.error)
        os.chmod.expect_call(mock.is_string_comparator(), stat.S_IRWXU)

        os.path.exists.expect_call(
                mock.is_string_comparator()).and_return(True)
        os.unlink.expect_call(mock.is_string_comparator())
        cls = server_job.base_server_job
        compare = mock.is_instance_comparator(cls)
        server_job.get_site_job_data.expect_call(compare).and_return({})
        utils.write_keyval.expect_call(mock.is_string_comparator(),
                                       mock.is_instance_comparator(dict))

        self.job = server_job.base_server_job(self.control,
                                              self.args,
                                              self.resultdir,
                                              self.label,
                                              self.user,
                                              self.machines)

        self.god.check_playback()

        # use this stub alot
        self.god.stub_function(self.job, "_execute_code")


    def test_init_parser(self):
        results = "results"
        log = os.path.join(results, '.parse.log')

        # do some additional setup
        self.god.stub_function(tko_utils, 'redirect_parser_debugging')
        self.god.stub_function(tko_db, 'db')
        self.god.stub_function(status_lib, 'parser')

        # set up recording
        file_obj = self.god.create_mock_class(file, "file")
        server_job.open.expect_call(log, 'w',
                                         0).and_return(file_obj)
        tko_utils.redirect_parser_debugging.expect_call(file_obj)
        db = self.god.create_mock_class(tko_db.db_sql, "db_sql")
        tko_db.db.expect_call(autocommit=True).and_return(db)
        parser = self.god.create_mock_class(parser_mod.parser, "parser_class")
        status_lib.parser.expect_call(1).and_return(parser)
        job_model = self.god.create_mock_class_obj(parser_mod0.job, "pjob")
        parser.make_job.expect_call(results).and_return(job_model)
        parser.start.expect_call(job_model)
        db.find_job.expect_call(mock.is_string_comparator())
        db.insert_job.expect_call(mock.is_string_comparator(),
                                  job_model)

        # run method
        self.job.init_parser(results)

        # check
        self.god.check_playback()


    def test_fill_server_control_namespace(self):
        class MockAutotest(object):
            job = None
        class MockHosts(object):
            job = None

        # Verify that the job attributes are injected in the expected place.
        self.god.stub_with(autotest, 'Autotest', MockAutotest)
        self.god.stub_with(hosts, 'Host', MockHosts)
        self.job._fill_server_control_namespace({})
        self.assertEqual(hosts.Host.job, self.job)
        self.assertEqual(autotest.Autotest.job, self.job)

        test_ns = {}
        self.job._fill_server_control_namespace(test_ns)

        # Verify that a few of the expected module exports were loaded.
        self.assertEqual(test_ns['sys'], sys)
        self.assert_('git' in test_ns)
        self.assert_('parallel_simple' in test_ns)
        self.assert_('sh_escape' in test_ns)
        self.assert_('barrier' in test_ns)
        self.assert_('format_error' in test_ns)
        self.assert_('AutoservRebootError' in test_ns)
        # This should not exist, client.common_lib.errors does not export it.
        self.assert_('format_exception' not in test_ns)

        # Replacing something that exists with something else is an error.
        orig_test_ns = {'hosts': 'not the autotest_lib.server.hosts module'}
        test_ns = orig_test_ns.copy()
        self.assertRaises(error.AutoservError,
                          self.job._fill_server_control_namespace, test_ns)

        # Replacing something that exists with something else is an error.
        test_ns = orig_test_ns.copy()
        self.assertRaises(error.AutoservError,
                          self.job._fill_server_control_namespace, test_ns)

        # Replacing something without protection should succeed.
        test_ns = orig_test_ns.copy()
        self.job._fill_server_control_namespace(test_ns, protect=False)
        self.assertEqual(test_ns['hosts'], hosts)

        # Replacing something with itself should issue a warning.
        test_ns = {'hosts': hosts}
        self.god.stub_function(warnings, 'showwarning')
        warnings.showwarning.expect_call(
                mock.is_instance_comparator(UserWarning), UserWarning,
                mock.is_string_comparator(), mock.is_instance_comparator(int))
        self.job._fill_server_control_namespace(test_ns)
        self.god.check_playback()
        self.assertEqual(test_ns['hosts'], hosts)


    def test_parallel_simple_with_one_machine(self):
        self.job.machines = ["hostname"]

        # setup
        func = self.god.create_mock_function("wrapper")

        # record
        func.expect_call("hostname")

        # run and check
        self.job.parallel_simple(func, self.job.machines)
        self.god.check_playback()


    def test_run_test(self):
        # setup
        self.god.stub_function(self.job.pkgmgr, 'get_package_name')
        self.god.stub_function(test, 'runtest')
        self.god.stub_function(self.job, 'record')

        # record
        url = "my.test.url"
        group = "group"
        testname = "testname"
        self.job.pkgmgr.get_package_name.expect_call(
            url, 'test').and_return((group, testname))
        outputdir = os.path.join(self.resultdir, testname)
        os.path.exists.expect_call(outputdir).and_return(False)
        os.mkdir.expect_call(outputdir)
        self.job.record.expect_call('START', testname, testname)
        test.runtest.expect_call(self.job, url, None, (), {})
        self.job.record.expect_call('GOOD', testname, testname,
                                    'completed successfully')
        self.job.record.expect_call('END GOOD', testname, testname)

        # run and check
        self.job.run_test(url)
        self.god.check_playback()


    def test_run_test_with_test_error(self):
        # setup
        self.god.stub_function(self.job.pkgmgr, 'get_package_name')
        self.god.stub_function(test, 'runtest')
        self.god.stub_function(self.job, 'record')

        # record
        url = "my.test.url"
        group = "group"
        testname = "testname"
        e = error.TestError("Unexpected error")
        self.job.pkgmgr.get_package_name.expect_call(
            url, 'test').and_return((group, testname))
        outputdir = os.path.join(self.resultdir, testname)
        os.path.exists.expect_call(outputdir).and_return(False)
        os.mkdir.expect_call(outputdir)
        self.job.record.expect_call('START', testname, testname)
        test.runtest.expect_call(self.job, url, None, (), {}).and_raises(e)
        self.job.record.expect_call('ERROR', testname, testname,
                                    'Unexpected error')
        self.job.record.expect_call('END ERROR', testname, testname)

        # run and check
        self.job.run_test(url)
        self.god.check_playback()


    def test_run_test_with_test_fail(self):
        # setup
        self.god.stub_function(self.job.pkgmgr, 'get_package_name')
        self.god.stub_function(test, 'runtest')
        self.god.stub_function(self.job, 'record')

        # record
        url = "my.test.url"
        group = "group"
        testname = "testname"
        e = error.TestFail("The test failed!")
        self.job.pkgmgr.get_package_name.expect_call(
            url, 'test').and_return((group, testname))
        outputdir = os.path.join(self.resultdir, testname)
        os.path.exists.expect_call(outputdir).and_return(False)
        os.mkdir.expect_call(outputdir)
        self.job.record.expect_call('START', testname, testname)
        test.runtest.expect_call(self.job, url, None, (), {}).and_raises(e)
        self.job.record.expect_call('FAIL', testname, testname,
                                    'The test failed!')
        self.job.record.expect_call('END FAIL', testname, testname)

        # run and check
        self.job.run_test(url)
        self.god.check_playback()


    def test_run_group(self):
        # setup
        func = self.god.create_mock_function("function")
        name = func.__name__
        self.god.stub_function(self.job, 'record')

        # record
        self.job.record.expect_call('START', None, name)
        func.expect_call((), {}).and_return(None)
        self.job.record.expect_call('END GOOD', None, name)

        # run and check
        self.job.run_group(func, (), {})
        self.god.check_playback()


    def test_run_reboot(self):
        # setup
        self.god.stub_function(self.job, 'record')
        reboot_func = self.god.create_mock_function('reboot')
        get_kernel_func = self.god.create_mock_function('get_kernel')
        kernel = '2.6.24'

        # record
        self.job.record.expect_call('START', None, 'reboot')
        reboot_func.expect_call()
        get_kernel_func.expect_call().and_return(kernel)
        self.job.record.expect_call('END GOOD', None, 'reboot',
                                    optional_fields={"kernel": kernel})

        # run and check
        self.job.run_reboot(reboot_func, get_kernel_func)
        self.god.check_playback()


    def test_run(self):
        self.god.stub_function(os, 'chdir')
        self.god.stub_function(tempfile, 'mkdtemp')
        self.god.stub_function(utils, 'open_write_close')
        self.god.stub_function(shutil, 'copy')
        self.god.stub_function(shutil, 'rmtree')
        control_files = []
        def _my_execute_code(control_file, namespace):
            control_files.append(control_file)
        self.god.stub_with(self.job, '_execute_code', _my_execute_code)

        self.job.args = ()
        self.job.ssh_user = None
        self.job.ssh_port = None
        self.job.ssh_pass = None
        self.job.control = 'fakecontrol'
        self.job.resultdir = '/xyz-unittest'

        def run_and_verify(control_file_executed):
            self.job.run(collect_crashdumps=False)
            self.assertEqual(1, len(control_files))
            self.assertEqual(control_file_executed, control_files[0])
            self.god.check_playback()
            control_files[:] = []

        # server with resultdir
        self.job.client = False
        os.chdir.expect_call(self.job.resultdir)
        utils.open_write_close.expect_any_call()
        run_and_verify(server_job.SERVER_CONTROL_FILENAME)

        # client with resultdir
        self.job.client = True
        os.chdir.expect_call(self.job.resultdir)
        utils.open_write_close.expect_call(server_job.CLIENT_CONTROL_FILENAME,
                                           'fakecontrol')
        shutil.copy.expect_call(server_job.CLIENT_WRAPPER_CONTROL_FILE,
                                server_job.SERVER_CONTROL_FILENAME)
        run_and_verify(server_job.SERVER_CONTROL_FILENAME)

        # Now test it without self.resultdir set.  It should try a mkdtemp dir.
        fake_tmp = '/tmp/fake'
        fake_server_control = os.path.join(fake_tmp,
                                           server_job.SERVER_CONTROL_FILENAME)
        fake_client_control = os.path.join(fake_tmp,
                                           server_job.CLIENT_CONTROL_FILENAME)
        self.job.resultdir = None

        # client without resultdir
        self.job.client = True
        tempfile.mkdtemp.expect_call().and_return(fake_tmp)
        utils.open_write_close.expect_call(fake_client_control, 'fakecontrol')
        shutil.copy.expect_any_call()
        shutil.rmtree.expect_call(fake_tmp)
        run_and_verify(fake_server_control)

        # server without resultdir
        self.job.client = False
        tempfile.mkdtemp.expect_call().and_return(fake_tmp)
        utils.open_write_close.expect_call(fake_server_control, 'fakecontrol')
        shutil.rmtree.expect_call(fake_tmp)
        run_and_verify(fake_server_control)


    def test_record(self):
        # setup
        self.god.stub_function(self.job, '_read_warnings')
        self.god.stub_function(self.job, '_record')
        status_code = 'GOOD'
        subdir = "subdir"
        operation = "operation"
        timestamp = '0'
        warnings = "danger, danger Will Robinson!"

        # record
        self.job._read_warnings.expect_call(
                ).and_return(((timestamp, warnings),))
        self.job._record.expect_call("WARN", None, None, warnings,
                                     timestamp)
        self.job._record.expect_call(status_code, subdir, operation, '',
                                     optional_fields=None)

        # run and check
        self.job.record(status_code, subdir, operation)
        self.god.check_playback()


if __name__ == "__main__":
    unittest.main()
