#!/usr/bin/python

import logging, os, unittest, shutil, sys, time, StringIO
import common

from autotest_lib.client.bin import job, boottool, config, sysinfo, harness
from autotest_lib.client.bin import test, xen, kernel, utils
from autotest_lib.client.common_lib import packages, error, log, logging_manager
from autotest_lib.client.common_lib import logging_config
from autotest_lib.client.common_lib.test_utils import mock


class Dummy(object):
    """A simple placeholder for attributes"""
    pass


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
        self.god.stub_class(job.local_host, 'LocalHost')
        self.god.stub_class(boottool, 'boottool')
        self.god.stub_class(sysinfo, 'sysinfo')

        self.god.stub_class_method(job.base_job, '_cleanup_results_dir')


    def tearDown(self):
        sys.stdout = sys.__stdout__
        self.god.unstub_all()


    def _setup_pre_record_init(self, cont):
        self.god.stub_function(self.job, '_init_group_level')
        self.god.stub_function(self.job, '_load_state')

        resultdir = os.path.join(self.autodir, 'results', self.jobtag)
        tmpdir = os.path.join(self.autodir, 'tmp')
        os.path.exists.expect_call(resultdir).and_return(False)
        os.makedirs.expect_call(resultdir)
        if not cont:
            job.base_job._cleanup_results_dir.expect_call()
            os.path.exists.expect_call(tmpdir).and_return(False)
            os.mkdir.expect_call(tmpdir)

        self.job._load_state.expect_call()
        self.job._init_group_level.expect_call()

        my_harness = self.god.create_mock_class(harness.harness,
                                                'my_harness')
        harness.select.expect_call(None,
                                   self.job).and_return(my_harness)

        return resultdir, my_harness


    def _setup_post_record_init(self, cont, resultdir, my_harness):
        # now some specific stubs
        self.god.stub_function(self.job, 'config_get')
        self.god.stub_function(self.job, 'config_set')
        self.god.stub_function(self.job, 'record')
        self.god.stub_function(self.job, '_increment_group_level')
        self.god.stub_function(self.job, '_decrement_group_level')
        self.god.stub_function(self.job, 'get_state')
        self.god.stub_function(self.job, 'set_state')

        # other setup
        results = os.path.join(self.autodir, 'results')
        download = os.path.join(self.autodir, 'tests', 'download')
        pkgdir = os.path.join(self.autodir, 'packages')

        utils.drop_caches.expect_call()
        self.job.get_state.expect_call("__run_test_cleanup",
                                       default=True).and_return(True)
        job_sysinfo = sysinfo.sysinfo.expect_new(resultdir)
        self.job.get_state.expect_call("__sysinfo",
                                       None).and_return(None)
        self.job.get_state.expect_call("__last_boot_tag",
                                       default=None).and_return(None)
        self.job.get_state.expect_call("__job_tag",
                                       default=None).and_return('1337-gps')
        if not cont:
            os.path.exists.expect_call(pkgdir).and_return(False)
            os.mkdir.expect_call(pkgdir)
            os.path.exists.expect_call(results).and_return(False)
            os.mkdir.expect_call(results)
            os.path.exists.expect_call(download).and_return(False)
            os.mkdir.expect_call(download)
            os.makedirs.expect_call(os.path.join(resultdir, 'analysis'))
            shutil.copyfile.expect_call(mock.is_string_comparator(),
                                 os.path.join(resultdir, 'control'))

        self.config = config.config.expect_new(self.job)
        job.local_host.LocalHost.expect_new(hostname='localhost')
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


    def construct_job(self, cont):
        # will construct class instance using __new__
        self.job = job.base_job.__new__(job.base_job)

        # record
        resultdir, my_harness = self._setup_pre_record_init(cont)
        self._setup_post_record_init(cont, resultdir, my_harness)

        # finish constructor
        options = Dummy()
        options.tag = self.jobtag
        options.cont = cont
        options.harness = None
        options.log = False
        options.verbose = False
        options.hostname = 'localhost'
        self.job.__init__(self.control, options,
                          extra_copy_cmdline=['more-blah'])

        # check
        self.god.check_playback()


    def get_partition_mock(self, devname):
        """
        Create a mock of a partition object and return it.
        """
        class mock(object):
            device = devname
            get_mountpoint = self.god.create_mock_function('get_mountpoint')
        return mock


    def test_constructor_first_run(self):
        self.construct_job(False)


    def test_constructor_continuation(self):
        self.construct_job(True)


    def test_constructor_post_record_failure(self):
        """
        Test post record initialization failure.
        """
        self.job = job.base_job.__new__(job.base_job)
        options = Dummy()
        options.tag = self.jobtag
        options.cont = False
        options.harness = None
        options.log = False
        options.verbose = False
        options.hostname = 'localhost'
        error = Exception('fail')

        self.god.stub_function(self.job, '_post_record_init')
        self.god.stub_function(self.job, 'record')

        self._setup_pre_record_init(False)
        self.job._post_record_init.expect_call(
                self.control, options, True, ['more-blah']).and_raises(error)
        self.job.record.expect_call(
                'ABORT', None, None,'client.bin.job.__init__ failed: %s' %
                str(error))

        self.assertRaises(
                Exception, self.job.__init__, self.control, options,
                drop_caches=True, extra_copy_cmdline=['more-blah'])

        # check
        self.god.check_playback()


    def test_monitor_disk_usage(self):
        self.construct_job(True)

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


    def test_report_reboot_failure(self):
        self.construct_job(True)

        # record
        self.job.record.expect_call("ABORT", "sub", "reboot.verify",
                                    "boot failure")
        self.job._decrement_group_level.expect_call()
        self.job.record.expect_call("END ABORT", "sub", "reboot",
                                    optional_fields={"kernel": "2.6.15-smp"})

        # playback
        self.job._record_reboot_failure("sub", "reboot.verify", "boot failure",
                                        running_id="2.6.15-smp")
        self.god.check_playback()


    def _setup_check_post_reboot(self, mount_info):
        # setup
        self.god.stub_function(job.partition_lib, "get_partition_list")

        part_list = [self.get_partition_mock("/dev/hda1"),
                     self.get_partition_mock("/dev/hdb1")]
        mount_list = ["/mnt/hda1", "/mnt/hdb1"]

        # record
        job.partition_lib.get_partition_list.expect_call(self.job).and_return(
                part_list)
        for i in xrange(len(part_list)):
            part_list[i].get_mountpoint.expect_call().and_return(mount_list[i])
        self.job.get_state.expect_call("__mount_info").and_return(mount_info)


    def test_check_post_reboot_success(self):
        self.construct_job(True)

        mount_info = set([("/dev/hda1", "/mnt/hda1"),
                          ("/dev/hdb1", "/mnt/hdb1")])
        self._setup_check_post_reboot(mount_info)

        # playback
        self.job._check_post_reboot("sub")
        self.god.check_playback()


    def test_check_post_reboot_mounts_failure(self):
        self.construct_job(True)

        mount_info = set([("/dev/hda1", "/mnt/hda1")])
        self._setup_check_post_reboot(mount_info)

        self.god.stub_function(self.job, "_record_reboot_failure")
        self.job._record_reboot_failure.expect_call("sub",
                "reboot.verify_config", "mounted partitions are different after"
                " reboot (old entries: set([]), new entries: set([('/dev/hdb1',"
                " '/mnt/hdb1')]))", running_id=None)

        # playback
        self.assertRaises(error.JobError, self.job._check_post_reboot, "sub")
        self.god.check_playback()


    def test_end_boot(self):
        self.construct_job(True)
        self.god.stub_function(self.job, "_check_post_reboot")

        # set up the job class
        self.job.group_level = 2

        self.job._check_post_reboot.expect_call("sub", running_id=None)
        self.job._decrement_group_level.expect_call()
        self.job.record.expect_call("END GOOD", "sub", "reboot",
                                    optional_fields={"kernel": "2.6.15-smp",
                                                     "patch0": "patchname"})

        # run test
        self.job.end_reboot("sub", "2.6.15-smp", ["patchname"])
        self.god.check_playback()


    def test_end_boot_and_verify_success(self):
        self.construct_job(True)
        self.god.stub_function(self.job, "_check_post_reboot")

        # set up the job class
        self.job.group_level = 2

        self.god.stub_function(utils, "running_os_ident")
        utils.running_os_ident.expect_call().and_return("2.6.15-smp")

        utils.read_one_line.expect_call("/proc/cmdline").and_return(
            "blah more-blah root=lala IDENT=81234567 blah-again")

        self.god.stub_function(utils, "running_os_full_version")
        running_id = "2.6.15-smp"
        utils.running_os_full_version.expect_call().and_return(running_id)

        self.job.record.expect_call("GOOD", "sub", "reboot.verify",
                                    running_id)
        self.job._check_post_reboot.expect_call("sub", running_id=running_id)
        self.job._decrement_group_level.expect_call()
        self.job.record.expect_call("END GOOD", "sub", "reboot",
                                    optional_fields={"kernel": running_id})

        # run test
        self.job.end_reboot_and_verify(81234567, "2.6.15-smp", "sub")
        self.god.check_playback()


    def test_end_boot_and_verify_failure(self):
        self.construct_job(True)
        self.god.stub_function(self.job, "_record_reboot_failure")

        # set up the job class
        self.job.group_level = 2

        self.god.stub_function(utils, "running_os_ident")
        utils.running_os_ident.expect_call().and_return("2.6.15-smp")

        utils.read_one_line.expect_call("/proc/cmdline").and_return(
            "blah more-blah root=lala IDENT=81234567 blah-again")

        self.job._record_reboot_failure.expect_call("sub", "reboot.verify",
                "boot failure", running_id="2.6.15-smp")

        # run test
        self.assertRaises(error.JobError, self.job.end_reboot_and_verify,
                          91234567, "2.6.16-smp", "sub")
        self.god.check_playback()


    def test_default_tag(self):
        self.construct_job(cont=False)

        self.job.set_state.expect_call("__job_tag", None)
        self.job.default_tag(None)
        self.assertEqual(None, self.job.tag)

        self.job.set_state.expect_call("__job_tag", '1337-gps')
        self.job.default_tag('1337-gps')
        self.assertEqual('1337-gps', self.job.tag)

        self.construct_job(cont=True)
        self.job.default_tag(None)
        self.god.check_playback()


if __name__ == "__main__":
    unittest.main()
