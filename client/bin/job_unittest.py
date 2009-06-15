#!/usr/bin/python

import logging, os, unittest, shutil, sys, time, StringIO
import common

from autotest_lib.client.bin import job, boottool, config, sysinfo, harness
from autotest_lib.client.bin import test, xen, kernel, utils
from autotest_lib.client.common_lib import packages, error, log, logging_manager
from autotest_lib.client.common_lib import logging_config
from autotest_lib.client.common_lib.test_utils import mock


class first_line_comparator(mock.argument_comparator):
    def __init__(self, first_line):
        self.first_line = first_line


    def is_satisfied_by(self, parameter):
        return self.first_line == parameter.splitlines()[0]


class TestBaseJob(unittest.TestCase):
    def setUp(self):
        # make god
        self.god = mock.mock_god()

        # need to set some environ variables
        self.autodir = "autodir"
        os.environ['AUTODIR'] = self.autodir

        # set up some variables
        self.control = "control"
        self.jobtag = "jobtag"

        # get rid of stdout and logging
        sys.stdout = StringIO.StringIO()
        logging_manager.configure_logging(logging_config.TestingConfig())
        logging.disable(logging.CRITICAL)
        def dummy_configure_logging(*args, **kwargs):
            pass
        self.god.stub_with(logging_manager, 'configure_logging',
                           dummy_configure_logging)
        real_get_logging_manager = logging_manager.get_logging_manager
        def get_logging_manager_no_fds(manage_stdout_and_stderr=False,
                                       redirect_fds=False):
            return real_get_logging_manager(manage_stdout_and_stderr, False)
        self.god.stub_with(logging_manager, 'get_logging_manager',
                           get_logging_manager_no_fds)

        # stub out some stuff
        self.god.stub_function(os.path, 'exists')
        self.god.stub_function(os.path, 'isdir')
        self.god.stub_function(os, 'makedirs')
        self.god.stub_function(os, 'mkdir')
        self.god.stub_function(os, 'remove')
        self.god.stub_function(shutil, 'rmtree')
        self.god.stub_function(shutil, 'copyfile')
        self.god.stub_function(job, 'open')
        self.god.stub_function(utils, 'system')
        self.god.stub_function(utils, 'drop_caches')
        self.god.stub_function(harness, 'select')
        self.god.stub_function(sysinfo, 'log_per_reboot_data')

        self.god.stub_class(config, 'config')
        self.god.stub_class(boottool, 'boottool')
        self.god.stub_class(sysinfo, 'sysinfo')

        self.god.stub_class_method(job.base_job, '_cleanup_results_dir')


    def tearDown(self):
        sys.stdout = sys.__stdout__
        self.god.unstub_all()


    def construct_job(self, cont):
        # will construct class instance using __new__
        self.job = job.base_job.__new__(job.base_job)

        # now some specific stubs
        self.god.stub_function(self.job, '_load_state')
        self.god.stub_function(self.job, '_init_group_level')
        self.god.stub_function(self.job, 'config_get')
        self.god.stub_function(self.job, 'config_set')
        self.god.stub_function(self.job, 'record')
        self.god.stub_function(self.job, '_increment_group_level')
        self.god.stub_function(self.job, '_decrement_group_level')
        self.god.stub_function(self.job, 'get_state')

        # other setup
        tmpdir = os.path.join(self.autodir, 'tmp')
        results = os.path.join(self.autodir, 'results')
        download = os.path.join(self.autodir, 'tests', 'download')
        resultdir = os.path.join(self.autodir, 'results', self.jobtag)
        pkgdir = os.path.join(self.autodir, 'packages')

        # record
        os.path.exists.expect_call(resultdir).and_return(False)
        os.makedirs.expect_call(resultdir)
        if not cont:
            job.base_job._cleanup_results_dir.expect_call()

        utils.drop_caches.expect_call()
        self.job._load_state.expect_call()
        self.job.get_state.expect_call("__run_test_cleanup",
                                       default=True).and_return(True)
        job_sysinfo = sysinfo.sysinfo.expect_new(resultdir)
        self.job.get_state.expect_call("__sysinfo",
                                       None).and_return(None)
        self.job.get_state.expect_call("__last_boot_tag",
                                       default=None).and_return(None)
        if not cont:
            os.path.exists.expect_call(tmpdir).and_return(False)
            os.mkdir.expect_call(tmpdir)
            os.path.exists.expect_call(pkgdir).and_return(False)
            os.mkdir.expect_call(pkgdir)
            os.path.exists.expect_call(results).and_return(False)
            os.mkdir.expect_call(results)
            os.path.exists.expect_call(download).and_return(False)
            os.mkdir.expect_call(download)
            os.makedirs.expect_call(os.path.join(resultdir, 'analysis'))
            shutil.copyfile.expect_call(mock.is_string_comparator(),
                                 os.path.join(resultdir, 'control'))

        self.job._init_group_level.expect_call()
        self.config = config.config.expect_new(self.job)
        my_harness = self.god.create_mock_class(harness.harness,
                                                'my_harness')
        harness.select.expect_call(None,
                                   self.job).and_return(my_harness)
        self.job.config_get.expect_call(
                'boottool.executable').and_return(None)
        bootloader = boottool.boottool.expect_new(None)
        job_sysinfo.log_per_reboot_data.expect_call()
        if not cont:
            self.job.record.expect_call('START', None, None)
            self.job._increment_group_level.expect_call()

        my_harness.run_start.expect_call()
        self.job.get_state.expect_call('__monitor_disk',
                                       default=0.0).and_return(0.0)

        self.god.stub_function(utils, 'read_one_line')
        utils.read_one_line.expect_call('/proc/cmdline').and_return(
            'blah more-blah root=lala IDENT=81234567 blah-again console=tty1')
        self.job.config_set.expect_call('boot.default_args',
                                        'more-blah console=tty1')
        # finish constructor
        self.job.__init__(self.control, self.jobtag, cont,
                          extra_copy_cmdline=['more-blah'])

        # check
        self.god.check_playback()


    def test_constructor(self):
        self.construct_job(False)


    def test_monitor_disk_usage(self):
        self.construct_job(True)

        # setup
        self.god.stub_function(self.job, 'set_state')

        # record
        max_rate = 10.0
        self.job.set_state.expect_call('__monitor_disk', max_rate)

        # test
        self.job.monitor_disk_usage(max_rate)
        self.god.check_playback()


    def test_relative_path(self):
        self.construct_job(True)
        dummy = "asdf"
        ret = self.job.relative_path(os.path.join(self.job.resultdir, dummy))
        self.assertEquals(ret, dummy)


    def test_control_functions(self):
        self.construct_job(True)
        control_file = "blah"
        self.job.control_set(control_file)
        self.assertEquals(self.job.control_get(), os.path.abspath(control_file))


    def test_harness_select(self):
        self.construct_job(True)

        # record
        which = "which"
        harness.select.expect_call(which, self.job).and_return(None)

        # run and test
        self.job.harness_select(which)
        self.god.check_playback()


    def test_config_set(self):
        self.construct_job(True)

        # unstub config_set
        self.god.unstub(self.job, 'config_set')
        # record
        name = "foo"
        val = 10
        self.config.set.expect_call(name, val)

        # run and test
        self.job.config_set(name, val)
        self.god.check_playback()


    def test_config_get(self):
        self.construct_job(True)

        # unstub config_get
        self.god.unstub(self.job, 'config_get')
        # record
        name = "foo"
        val = 10
        self.config.get.expect_call(name).and_return(val)

        # run and test
        self.job.config_get(name)
        self.god.check_playback()


    def test_setup_dirs_raise(self):
        self.construct_job(True)

        # setup
        results_dir = 'foo'
        tmp_dir = 'bar'

        # record
        os.path.exists.expect_call(tmp_dir).and_return(True)
        os.path.isdir.expect_call(tmp_dir).and_return(False)

        # test
        self.assertRaises(ValueError, self.job.setup_dirs, results_dir, tmp_dir)
        self.god.check_playback()


    def test_setup_dirs(self):
        self.construct_job(True)

        # setup
        results_dir1 = os.path.join(self.job.resultdir, 'build')
        results_dir2 = os.path.join(self.job.resultdir, 'build.2')
        results_dir3 = os.path.join(self.job.resultdir, 'build.3')
        tmp_dir = 'bar'

        # record
        os.path.exists.expect_call(tmp_dir).and_return(False)
        os.mkdir.expect_call(tmp_dir)
        os.path.isdir.expect_call(tmp_dir).and_return(True)
        os.path.exists.expect_call(results_dir1).and_return(True)
        os.path.exists.expect_call(results_dir2).and_return(True)
        os.path.exists.expect_call(results_dir3).and_return(False)
        os.path.exists.expect_call(results_dir3).and_return(False)
        os.mkdir.expect_call(results_dir3)

        # test
        self.assertEqual(self.job.setup_dirs(None, tmp_dir),
                         (results_dir3, tmp_dir))
        self.god.check_playback()


    def test_xen(self):
        self.construct_job(True)

        # setup
        self.god.stub_function(self.job, "setup_dirs")
        self.god.stub_class(xen, "xen")
        results = 'results_dir'
        tmp = 'tmp'
        build = 'xen'
        base_tree = object()

        # record
        self.job.setup_dirs.expect_call(results,
                                        tmp).and_return((results, tmp))
        myxen = xen.xen.expect_new(self.job, base_tree, results, tmp, build,
                                   False, None)

        # run job and check
        axen = self.job.xen(base_tree, results, tmp)
        self.god.check_playback()
        self.assertEquals(myxen, axen)


    def test_kernel_rpm(self):
        self.construct_job(True)

        # setup
        self.god.stub_function(self.job, "setup_dirs")
        self.god.stub_class(kernel, "rpm_kernel")
        self.god.stub_function(kernel, "preprocess_path")
        self.god.stub_function(self.job.pkgmgr, "fetch_pkg")
        self.god.stub_function(utils, "get_os_vendor")
        results = 'results_dir'
        tmp = 'tmp'
        build = 'xen'
        path = "somepath.rpm"
        packages_dir = os.path.join("autodir/packages", path)

        # record
        self.job.setup_dirs.expect_call(results,
                                        tmp).and_return((results, tmp))
        kernel.preprocess_path.expect_call(path).and_return(path)
        os.path.exists.expect_call(path).and_return(False)
        self.job.pkgmgr.fetch_pkg.expect_call(path, packages_dir, repo_url='')
        utils.get_os_vendor.expect_call()
        mykernel = kernel.rpm_kernel.expect_new(self.job, [packages_dir],
                                                results)

        # check
        akernel = self.job.kernel(path, results, tmp)
        self.god.check_playback()
        self.assertEquals(mykernel, akernel)


    def test_kernel(self):
        self.construct_job(True)

        # setup
        self.god.stub_function(self.job, "setup_dirs")
        self.god.stub_class(kernel, "kernel")
        self.god.stub_function(kernel, "preprocess_path")
        results = 'results_dir'
        tmp = 'tmp'
        build = 'linux'
        path = "somepath.deb"

        # record
        self.job.setup_dirs.expect_call(results,
                                        tmp).and_return((results, tmp))
        kernel.preprocess_path.expect_call(path).and_return(path)
        mykernel = kernel.kernel.expect_new(self.job, path, results, tmp,
                                            build, False)

        # check
        akernel = self.job.kernel(path, results, tmp)
        self.god.check_playback()
        self.assertEquals(mykernel, akernel)


    def test_run_test_logs_test_error_from_unhandled_error(self):
        self.construct_job(True)

        # set up stubs
        self.god.stub_function(self.job.pkgmgr, 'get_package_name')
        self.god.stub_function(self.job, "_runtest")

        # create an unhandled error object
        class MyError(error.TestError):
            pass
        real_error = MyError("this is the real error message")
        unhandled_error = error.UnhandledTestError(real_error)

        # set up the recording
        testname = "error_test"
        outputdir = os.path.join(self.job.resultdir, testname)
        self.job.pkgmgr.get_package_name.expect_call(
            testname, 'test').and_return(("", testname))
        self.job.get_state.expect_call(
                self.job._RUN_NUMBER_STATE, default=0).and_return(0)
        self.job.get_state.expect_call(
                self.job._KERNEL_IN_TAG_STATE, default=False).and_return(False)
        os.path.exists.expect_call(outputdir).and_return(False)
        os.mkdir.expect_call(outputdir)
        self.job.record.expect_call("START", testname, testname)
        self.job._increment_group_level.expect_call()
        self.job._runtest.expect_call(testname, "", (), {}).and_raises(
            unhandled_error)
        self.job.record.expect_call("ERROR", testname, testname,
                                    first_line_comparator(str(real_error)))
        self.job._decrement_group_level.expect_call()
        self.job.record.expect_call("END ERROR", testname, testname)
        self.job.harness.run_test_complete.expect_call()
        utils.drop_caches.expect_call()

        # run and check
        self.job.run_test(testname)
        self.god.check_playback()


    def test_run_test_logs_non_test_error_from_unhandled_error(self):
        self.construct_job(True)

        # set up stubs
        self.god.stub_function(self.job.pkgmgr, 'get_package_name')
        self.god.stub_function(self.job, "_runtest")

        # create an unhandled error object
        class MyError(Exception):
            pass
        real_error = MyError("this is the real error message")
        unhandled_error = error.UnhandledTestError(real_error)
        reason = first_line_comparator("Unhandled MyError: %s" % real_error)

        # set up the recording
        testname = "error_test"
        outputdir = os.path.join(self.job.resultdir, testname)
        self.job.pkgmgr.get_package_name.expect_call(
            testname, 'test').and_return(("", testname))
        self.job.get_state.expect_call(
                self.job._RUN_NUMBER_STATE, default=0).and_return(0)
        self.job.get_state.expect_call(
                self.job._KERNEL_IN_TAG_STATE, default=False).and_return(False)
        os.path.exists.expect_call(outputdir).and_return(False)
        os.mkdir.expect_call(outputdir)
        self.job.record.expect_call("START", testname, testname)
        self.job._increment_group_level.expect_call()
        self.job._runtest.expect_call(testname, "", (), {}).and_raises(
            unhandled_error)
        self.job.record.expect_call("ERROR", testname, testname, reason)
        self.job._decrement_group_level.expect_call()
        self.job.record.expect_call("END ERROR", testname, testname)
        self.job.harness.run_test_complete.expect_call()
        utils.drop_caches.expect_call()

        # run and check
        self.job.run_test(testname)
        self.god.check_playback()


    def test_record(self):
        self.construct_job(True)

        # steup
        self.job.group_level = 1
        status = ''
        status_code = "PASS"
        subdir = "subdir"
        operation = "super_fun"
        mytime = "1234"
        msg_tag = ""
        if "." in self.job.log_filename:
            msg_tag = self.job.log_filename.split(".", 1)[1]
        epoch_time = int(mytime)
        local_time = time.localtime(epoch_time)
        optional_fields = {}
        optional_fields["timestamp"] = str(epoch_time)
        optional_fields["localtime"] = time.strftime("%b %d %H:%M:%S",
                                                     local_time)
        fields = [status_code, subdir, operation]
        fields += ["%s=%s" % x for x in optional_fields.iteritems()]
        fields.append(status)
        msg = '\t'.join(str(x) for x in fields)
        msg = '\t' * self.job.group_level + msg

        self.god.stub_function(log, "is_valid_status")
        self.god.stub_function(time, "time")
        self.god.stub_function(self.job, "open")


        # record
        log.is_valid_status.expect_call(status_code).and_return(True)
        time.time.expect_call().and_return(mytime)
        self.job.harness.test_status_detail.expect_call(status_code, subdir,
                                                        operation, '', msg_tag)
        self.job.harness.test_status.expect_call(msg, msg_tag)
        myfile = self.god.create_mock_class(file, "file")
        status_file = os.path.join(self.job.resultdir, self.job.log_filename)
        self.job.open.expect_call(status_file, "a").and_return(myfile)
        myfile.write.expect_call(msg + "\n")

        dir = os.path.join(self.job.resultdir, subdir)
        status_file = os.path.join(dir, self.job.DEFAULT_LOG_FILENAME)
        self.job.open.expect_call(status_file, "a").and_return(myfile)
        myfile.write.expect_call(msg + "\n")


        # run test
        self.god.unstub(self.job, "record")
        self.job.record(status_code, subdir, operation)
        self.god.check_playback()


    def test_end_boot(self):
        self.construct_job(True)

        # set up the job class
        self.job.group_level = 2

        self.job._decrement_group_level.expect_call()
        self.job.record.expect_call("END GOOD", "sub", "reboot",
                                    optional_fields={"kernel": "2.6.15-smp",
                                                     "patch0": "patchname"})

        # run test
        self.job.end_reboot("sub", "2.6.15-smp", ["patchname"])
        self.god.check_playback()


    def test_end_boot_and_verify_success(self):
        self.construct_job(True)

        # set up the job class
        self.job.group_level = 2

        self.god.stub_function(utils, "running_os_ident")
        utils.running_os_ident.expect_call().and_return("2.6.15-smp")

        utils.read_one_line.expect_call("/proc/cmdline").and_return(
            "blah more-blah root=lala IDENT=81234567 blah-again")

        self.god.stub_function(utils, "running_os_full_version")
        utils.running_os_full_version.expect_call().and_return("2.6.15-smp")

        self.job.record.expect_call("GOOD", "sub", "reboot.verify",
                                    "2.6.15-smp")
        self.job._decrement_group_level.expect_call()
        self.job.record.expect_call("END GOOD", "sub", "reboot",
                                    optional_fields={"kernel": "2.6.15-smp"})

        # run test
        self.job.end_reboot_and_verify(81234567, "2.6.15-smp", "sub")
        self.god.check_playback()


    def test_end_boot_and_verify_failure(self):
        self.construct_job(True)

        # set up the job class
        self.job.group_level = 2

        self.god.stub_function(utils, "running_os_ident")
        utils.running_os_ident.expect_call().and_return("2.6.15-smp")

        utils.read_one_line.expect_call("/proc/cmdline").and_return(
            "blah more-blah root=lala IDENT=81234567 blah-again")

        self.job.record.expect_call("ABORT", "sub", "reboot.verify",
                                    "boot failure")
        self.job._decrement_group_level.expect_call()
        self.job.record.expect_call("END ABORT", "sub", "reboot",
                                    optional_fields={"kernel": "2.6.15-smp"})

        # run test
        self.assertRaises(error.JobError, self.job.end_reboot_and_verify,
                          91234567, "2.6.16-smp", "sub")
        self.god.check_playback()


if __name__ == "__main__":
    unittest.main()
