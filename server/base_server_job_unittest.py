#!/usr/bin/python

import unittest, os, time
import common
from autotest_lib.server import base_server_job, test, subcommand
from autotest_lib.client.common_lib import utils, error, host_protections
from autotest_lib.tko import db as tko_db, status_lib, utils as tko_utils
from autotest_lib.client.common_lib.test_utils import mock
from autotest_lib.tko.parsers import version_1 as parser_mod
from autotest_lib.tko.parsers import version_0 as parser_mod0


class BaseServerJobTest(unittest.TestCase):
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
        self.god.stub_function(os, 'chdir')
        self.god.stub_function(os, 'unlink')
        self.god.stub_function(base_server_job, 'get_site_job_data')
        self.god.stub_function(base_server_job, 'open')
        self.god.stub_function(utils, 'write_keyval')




    def tearDown(self):
        self.god.unstub_all()


    def construct_server_job(self):
        # setup recording for constructor
        file_obj = self.god.create_mock_class(file, "file")
        base_server_job.open.expect_call(self.control,
                                         'r').and_return(file_obj)
        file_obj.read.expect_call().and_return('')
        os.path.exists.expect_call(
                mock.is_string_comparator()).and_return(False)
        os.mkdir.expect_call(mock.is_string_comparator())
        os.path.exists.expect_call(
                mock.is_string_comparator()).and_return(False)
        os.mkdir.expect_call(mock.is_string_comparator())
        os.path.exists.expect_call(
                mock.is_string_comparator()).and_return(True)
        os.unlink.expect_call(mock.is_string_comparator())
        cls = base_server_job.base_server_job
        compare = mock.is_instance_comparator(cls)
        base_server_job.get_site_job_data.expect_call(
                compare).and_return({})
        utils.write_keyval.expect_call(mock.is_string_comparator(),
                                       mock.is_instance_comparator(dict))

        self.job = base_server_job.base_server_job(self.control,
                                                   self.args,
                                                   self.resultdir,
                                                   self.label,
                                                   self.user,
                                                   self.machines)

        self.god.check_playback()

        # use this stub alot
        self.god.stub_function(self.job, "_execute_code")


    def test_constructor(self):
        self.construct_server_job()


    def test_init_parser(self):
        self.construct_server_job()

        results = "results"
        log = os.path.join(results, '.parse.log')

        # do some additional setup
        self.god.stub_function(tko_utils, 'redirect_parser_debugging')
        self.god.stub_function(tko_db, 'db')
        self.god.stub_function(status_lib, 'parser')

        # set up recording
        file_obj = self.god.create_mock_class(file, "file")
        base_server_job.open.expect_call(log, 'w',
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


    def test_verify(self):
        self.construct_server_job()

        # record
        namespace = {'machines' : self.machines, 'job' : self.job, \
                     'ssh_user' : self.job.ssh_user, \
                     'ssh_port' : self.job.ssh_port, \
                     'ssh_pass' : self.job.ssh_pass}
        arg = base_server_job.preamble + base_server_job.verify
        self.job._execute_code.expect_call(arg, namespace,
                                                namespace)

        # run and check
        self.job.verify()
        self.god.check_playback()


    def test_repair(self):
        self.construct_server_job()

        # record
        verify_namespace = {'machines' : self.machines, 'job' : self.job,
                            'ssh_user' : self.job.ssh_user,
                            'ssh_port' : self.job.ssh_port,
                            'ssh_pass' : self.job.ssh_pass}
        repair_namespace = verify_namespace.copy()
        repair_namespace['protection_level'] = host_protections.default

        arg = base_server_job.preamble + base_server_job.repair
        self.job._execute_code.expect_call(arg, repair_namespace,
                                           repair_namespace)
        arg = base_server_job.preamble + base_server_job.verify
        self.job._execute_code.expect_call(arg, verify_namespace,
                                           verify_namespace)

        # run and check
        self.job.repair(host_protections.default)
        self.god.check_playback()


    def test_parallel_simple(self):
        self.construct_server_job()

        # setup
        func = self.god.create_mock_function("wrapper")
        self.god.stub_function(subcommand, 'parallel_simple')

        # record
        subcommand.parallel_simple.expect_call(func, self.machines,
                                                True, None)

        # run and check
        self.job.parallel_simple(func, self.machines)
        self.god.check_playback()


    def test_run(self):
        self.construct_server_job()

        # setup
        self.god.stub_function(time, 'time')
        self.god.stub_function(self.job, 'enable_external_logging')
        self.god.stub_function(self.job, 'disable_external_logging')
        file_obj = self.god.create_mock_class(file, "file")
        namespace = {}
        my_time = 0.0
        namespace['machines'] = self.machines
        namespace['args'] = self.args
        namespace['job'] = self.job
        namespace['ssh_user'] = self.job.ssh_user
        namespace['ssh_port'] = self.job.ssh_port
        namespace['ssh_pass'] = self.job.ssh_pass
        namespace2 = {}
        namespace2['machines'] = self.machines
        namespace2['args'] = self.args
        namespace2['job'] = self.job
        namespace2['ssh_user'] = self.job.ssh_user
        namespace2['ssh_port'] = self.job.ssh_port
        namespace2['ssh_pass'] = self.job.ssh_pass
        namespace2['test_start_time'] = int(my_time)

        # record
        time.time.expect_call().and_return(my_time)
        os.chdir.expect_call(mock.is_string_comparator())
        self.job.enable_external_logging.expect_call()
        base_server_job.open.expect_call(
                'control.srv', 'w').and_return(file_obj)
        file_obj.write.expect_call('')
        arg = base_server_job.preamble + ''
        self.job._execute_code.expect_call(arg, namespace,
                                                namespace)
        arg = base_server_job.preamble + base_server_job.crashdumps
        self.job._execute_code.expect_call(arg, namespace2,
                                                namespace2)
        self.job.disable_external_logging.expect_call()

        # run and check
        self.job.run()
        self.god.check_playback()


    def test_run_test(self):
        self.construct_server_job()

        # setup
        self.god.stub_function(test, 'testname')
        self.god.stub_function(test, 'runtest')
        self.god.stub_function(self.job, 'record')

        # record
        url = "my.test.url"
        group = "group"
        testname = "testname"
        test.testname.expect_call(url).and_return((group, testname))
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
        self.construct_server_job()

        # setup
        self.god.stub_function(test, 'testname')
        self.god.stub_function(test, 'runtest')
        self.god.stub_function(self.job, 'record')

        # record
        url = "my.test.url"
        group = "group"
        testname = "testname"
        e = error.TestError("Unexpected error")
        test.testname.expect_call(url).and_return((group, testname))
        outputdir = os.path.join(self.resultdir, testname)
        os.path.exists.expect_call(outputdir).and_return(False)
        os.mkdir.expect_call(outputdir)
        self.job.record.expect_call('START', testname, testname)
        test.runtest.expect_call(self.job, url, None, (), {}).and_raises(e)
        self.job.record.expect_call('ERROR', testname, testname,
                                    'Unexpected error')
        self.job.record.expect_call('END ERROR', testname, testname,
                                    'Unexpected error')

        # run and check
        self.job.run_test(url)
        self.god.check_playback()


    def test_run_test_with_test_fail(self):
        self.construct_server_job()

        # setup
        self.god.stub_function(test, 'testname')
        self.god.stub_function(test, 'runtest')
        self.god.stub_function(self.job, 'record')

        # record
        url = "my.test.url"
        group = "group"
        testname = "testname"
        e = error.TestFail("The test failed!")
        test.testname.expect_call(url).and_return((group, testname))
        outputdir = os.path.join(self.resultdir, testname)
        os.path.exists.expect_call(outputdir).and_return(False)
        os.mkdir.expect_call(outputdir)
        self.job.record.expect_call('START', testname, testname)
        test.runtest.expect_call(self.job, url, None, (), {}).and_raises(e)
        self.job.record.expect_call('FAIL', testname, testname,
                                    'The test failed!')
        self.job.record.expect_call('END FAIL', testname, testname,
                                    'The test failed!')

        # run and check
        self.job.run_test(url)
        self.god.check_playback()


    def test_run_group(self):
        self.construct_server_job()

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
        self.construct_server_job()

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


    def test_record(self):
        self.construct_server_job()

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
