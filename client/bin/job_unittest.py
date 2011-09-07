#!/usr/bin/python

import logging, os, shutil, sys, time, StringIO
import common

from autotest_lib.client.bin import job, boottool, config, sysinfo, harness
from autotest_lib.client.bin import test, xen, kernel, utils
from autotest_lib.client.common_lib import packages, error, log
from autotest_lib.client.common_lib import logging_manager, logging_config
from autotest_lib.client.common_lib import base_job_unittest
from autotest_lib.client.common_lib.test_utils import mock, unittest


class job_test_case(unittest.TestCase):
    """Generic job TestCase class that defines a standard job setUp and
    tearDown, with some standard stubs."""

    job_class = job.base_client_job

    def setUp(self):
        self.god = mock.mock_god(ut=self)
        self.god.stub_with(job.base_client_job, '_get_environ_autodir',
                           classmethod(lambda cls: '/adir'))
        self.job = self.job_class.__new__(self.job_class)
        self.job._job_directory = base_job_unittest.stub_job_directory


    def tearDown(self):
        self.god.unstub_all()


class test_find_base_directories(
        base_job_unittest.test_find_base_directories.generic_tests,
        job_test_case):

    def test_autodir_equals_clientdir(self):
        autodir, clientdir, _ = self.job._find_base_directories()
        self.assertEqual(autodir, '/adir')
        self.assertEqual(clientdir, '/adir')


    def test_serverdir_is_none(self):
        _, _, serverdir = self.job._find_base_directories()
        self.assertEqual(serverdir, None)


class abstract_test_init(base_job_unittest.test_init.generic_tests):
    """Generic client job mixin used when defining variations on the
    job.__init__ generic tests."""
    OPTIONAL_ATTRIBUTES = (
        base_job_unittest.test_init.generic_tests.OPTIONAL_ATTRIBUTES
        - set(['control', 'bootloader', 'harness']))


class test_init_minimal_options(abstract_test_init, job_test_case):
    def call_init(self):
        # TODO(jadmanski): refactor more of the __init__ code to not need to
        # stub out countless random APIs
        self.god.stub_function_to_return(job.os, 'mkdir', None)
        self.god.stub_function_to_return(job.os.path, 'exists', True)
        self.god.stub_function_to_return(self.job, '_load_state', None)
        self.god.stub_function_to_return(self.job, 'record', None)
        self.god.stub_function_to_return(job.shutil, 'copyfile', None)
        self.god.stub_function_to_return(job.logging_manager,
                                         'configure_logging', None)
        class manager:
            def start_logging(self):
                return None
        self.god.stub_function_to_return(job.logging_manager,
                                         'get_logging_manager', manager())
        class stub_sysinfo:
            def log_per_reboot_data(self):
                return None
        self.god.stub_function_to_return(job.sysinfo, 'sysinfo',
                                         stub_sysinfo())
        class stub_harness:
            run_start = lambda self: None
        self.god.stub_function_to_return(job.harness, 'select', stub_harness())
        self.god.stub_function_to_return(job.boottool, 'boottool', object())
        class options:
            tag = ''
            verbose = False
            cont = False
            harness = 'stub'
            harness_args = None
            hostname = None
            user = None
            log = False
            args = ''
            output_dir = ''
            tap_report = None
        self.god.stub_function_to_return(job.utils, 'drop_caches', None)

        self.job._job_state = base_job_unittest.stub_job_state
        self.job.__init__('/control', options)


class dummy(object):
    """A simple placeholder for attributes"""
    pass


class first_line_comparator(mock.argument_comparator):
    def __init__(self, first_line):
        self.first_line = first_line


    def is_satisfied_by(self, parameter):
        return self.first_line == parameter.splitlines()[0]


class test_base_job(unittest.TestCase):
    def setUp(self):
        # make god
        self.god = mock.mock_god(ut=self)

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

        self.god.stub_class_method(job.base_client_job,
                                   '_cleanup_debugdir_files')
        self.god.stub_class_method(job.base_client_job, '_cleanup_results_dir')

        self.god.stub_with(job.base_job.job_directory, '_ensure_valid',
                           lambda *_: None)


    def tearDown(self):
        sys.stdout = sys.__stdout__
        self.god.unstub_all()


    def _setup_pre_record_init(self, cont):
        self.god.stub_function(self.job, '_load_state')

        resultdir = os.path.join(self.autodir, 'results', self.jobtag)
        tmpdir = os.path.join(self.autodir, 'tmp')
        if not cont:
            job.base_client_job._cleanup_debugdir_files.expect_call()
            job.base_client_job._cleanup_results_dir.expect_call()

        self.job._load_state.expect_call()

        my_harness = self.god.create_mock_class(harness.harness,
                                                'my_harness')
        harness.select.expect_call(None,
                                   self.job,
                                   None).and_return(my_harness)

        return resultdir, my_harness


    def _setup_post_record_init(self, cont, resultdir, my_harness):
        # now some specific stubs
        self.god.stub_function(self.job, 'config_get')
        self.god.stub_function(self.job, 'config_set')
        self.god.stub_function(self.job, 'record')

        # other setup
        results = os.path.join(self.autodir, 'results')
        download = os.path.join(self.autodir, 'tests', 'download')
        pkgdir = os.path.join(self.autodir, 'packages')

        utils.drop_caches.expect_call()
        job_sysinfo = sysinfo.sysinfo.expect_new(resultdir)
        if not cont:
            os.path.exists.expect_call(download).and_return(False)
            os.mkdir.expect_call(download)
            shutil.copyfile.expect_call(mock.is_string_comparator(),
                                 os.path.join(resultdir, 'control'))

        self.config = config.config.expect_new(self.job)
        self.job.config_get.expect_call(
                'boottool.executable').and_return(None)
        bootloader = boottool.boottool.expect_new(None)
        job.local_host.LocalHost.expect_new(hostname='localhost',
                                            bootloader=bootloader)
        job_sysinfo.log_per_reboot_data.expect_call()
        if not cont:
            self.job.record.expect_call('START', None, None)

        my_harness.run_start.expect_call()

        self.god.stub_function(utils, 'read_one_line')
        utils.read_one_line.expect_call('/proc/cmdline').and_return(
            'blah more-blah root=lala IDENT=81234567 blah-again console=tty1')
        self.job.config_set.expect_call('boot.default_args',
                                        'more-blah console=tty1')


    def construct_job(self, cont):
        # will construct class instance using __new__
        self.job = job.base_client_job.__new__(job.base_client_job)

        # record
        resultdir, my_harness = self._setup_pre_record_init(cont)
        self._setup_post_record_init(cont, resultdir, my_harness)

        # finish constructor
        options = dummy()
        options.tag = self.jobtag
        options.cont = cont
        options.harness = None
        options.harness_args = None
        options.log = False
        options.verbose = False
        options.hostname = 'localhost'
        options.user = 'my_user'
        options.args = ''
        options.output_dir = ''
        options.tap_report = None
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
        self.job = job.base_client_job.__new__(job.base_client_job)
        options = dummy()
        options.tag = self.jobtag
        options.cont = False
        options.harness = None
        options.harness_args = None
        options.log = False
        options.verbose = False
        options.hostname = 'localhost'
        options.user = 'my_user'
        options.args = ''
        options.output_dir = ''
        options.tap_report = None
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
        harness_args = ''
        harness.select.expect_call(which, self.job, 
                                   harness_args).and_return(None)

        # run and test
        self.job.harness_select(which, harness_args)
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
        os.path.exists.expect_call(outputdir).and_return(False)
        self.job.record.expect_call("START", testname, testname,
                                    optional_fields=None)
        self.job._runtest.expect_call(testname, "", None, (), {}).and_raises(
            unhandled_error)
        self.job.record.expect_call("ERROR", testname, testname,
                                    first_line_comparator(str(real_error)))
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
        os.path.exists.expect_call(outputdir).and_return(False)
        self.job.record.expect_call("START", testname, testname,
                                    optional_fields=None)
        self.job._runtest.expect_call(testname, "", None, (), {}).and_raises(
            unhandled_error)
        self.job.record.expect_call("ERROR", testname, testname, reason)
        self.job.record.expect_call("END ERROR", testname, testname)
        self.job.harness.run_test_complete.expect_call()
        utils.drop_caches.expect_call()

        # run and check
        self.job.run_test(testname)
        self.god.check_playback()


    def test_report_reboot_failure(self):
        self.construct_job(True)

        # record
        self.job.record.expect_call("ABORT", "sub", "reboot.verify",
                                    "boot failure")
        self.job.record.expect_call("END ABORT", "sub", "reboot",
                                    optional_fields={"kernel": "2.6.15-smp"})

        # playback
        self.job._record_reboot_failure("sub", "reboot.verify", "boot failure",
                                        running_id="2.6.15-smp")
        self.god.check_playback()


    def _setup_check_post_reboot(self, mount_info, cpu_count):
        # setup
        self.god.stub_function(job.partition_lib, "get_partition_list")
        self.god.stub_function(utils, "count_cpus")

        part_list = [self.get_partition_mock("/dev/hda1"),
                     self.get_partition_mock("/dev/hdb1")]
        mount_list = ["/mnt/hda1", "/mnt/hdb1"]

        # record
        job.partition_lib.get_partition_list.expect_call(
                self.job, exclude_swap=False).and_return(part_list)
        for i in xrange(len(part_list)):
            part_list[i].get_mountpoint.expect_call().and_return(mount_list[i])
        if cpu_count is not None:
            utils.count_cpus.expect_call().and_return(cpu_count)
        self.job._state.set('client', 'mount_info', mount_info)
        self.job._state.set('client', 'cpu_count', 8)


    def test_check_post_reboot_success(self):
        self.construct_job(True)

        mount_info = set([("/dev/hda1", "/mnt/hda1"),
                          ("/dev/hdb1", "/mnt/hdb1")])
        self._setup_check_post_reboot(mount_info, 8)

        # playback
        self.job._check_post_reboot("sub")
        self.god.check_playback()


    def test_check_post_reboot_mounts_failure(self):
        self.construct_job(True)

        mount_info = set([("/dev/hda1", "/mnt/hda1")])
        self._setup_check_post_reboot(mount_info, None)

        self.god.stub_function(self.job, "_record_reboot_failure")
        self.job._record_reboot_failure.expect_call("sub",
                "reboot.verify_config", "mounted partitions are different after"
                " reboot (old entries: set([]), new entries: set([('/dev/hdb1',"
                " '/mnt/hdb1')]))", running_id=None)

        # playback
        self.assertRaises(error.JobError, self.job._check_post_reboot, "sub")
        self.god.check_playback()


    def test_check_post_reboot_cpu_failure(self):
        self.construct_job(True)

        mount_info = set([("/dev/hda1", "/mnt/hda1"),
                          ("/dev/hdb1", "/mnt/hdb1")])
        self._setup_check_post_reboot(mount_info, 4)

        self.god.stub_function(self.job, "_record_reboot_failure")
        self.job._record_reboot_failure.expect_call(
            'sub', 'reboot.verify_config',
            'Number of CPUs changed after reboot (old count: 8, new count: 4)',
            running_id=None)

        # playback
        self.assertRaises(error.JobError, self.job._check_post_reboot, "sub")
        self.god.check_playback()


    def test_end_boot(self):
        self.construct_job(True)
        self.god.stub_function(self.job, "_check_post_reboot")

        # set up the job class
        self.job._record_prefix = '\t\t'

        self.job._check_post_reboot.expect_call("sub", running_id=None)
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
        self.job._record_prefix = '\t\t'

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
        self.job.record.expect_call("END GOOD", "sub", "reboot",
                                    optional_fields={"kernel": running_id})

        # run test
        self.job.end_reboot_and_verify(81234567, "2.6.15-smp", "sub")
        self.god.check_playback()


    def test_end_boot_and_verify_failure(self):
        self.construct_job(True)
        self.god.stub_function(self.job, "_record_reboot_failure")

        # set up the job class
        self.job._record_prefix = '\t\t'

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


    def test_parse_args(self):
        test_set = {"a='foo bar baz' b='moo apt'":
                    ["a='foo bar baz'", "b='moo apt'"],
                    "a='foo bar baz' only=gah":
                    ["a='foo bar baz'", "only=gah"],
                    "a='b c d' no=argh":
                    ["a='b c d'", "no=argh"]}
        for t in test_set:
            parsed_args = job.base_client_job._parse_args(t)
            expected_args = test_set[t]
            self.assertEqual(parsed_args, expected_args)


    def test_run_test_timeout_parameter_is_propagated(self):
        self.construct_job(True)

        # set up stubs
        self.god.stub_function(self.job.pkgmgr, 'get_package_name')
        self.god.stub_function(self.job, "_runtest")

        # create an unhandled error object
        #class MyError(error.TestError):
        #    pass
        #real_error = MyError("this is the real error message")
        #unhandled_error = error.UnhandledTestError(real_error)

        # set up the recording
        testname = "test"
        outputdir = os.path.join(self.job.resultdir, testname)
        self.job.pkgmgr.get_package_name.expect_call(
            testname, 'test').and_return(("", testname))
        os.path.exists.expect_call(outputdir).and_return(False)
        timeout = 60
        optional_fields = {}
        optional_fields['timeout'] = timeout
        self.job.record.expect_call("START", testname, testname,
                                    optional_fields=optional_fields)
        self.job._runtest.expect_call(testname, "", timeout, (), {})
        self.job.record.expect_call("GOOD", testname, testname,
                                    "completed successfully")
        self.job.record.expect_call("END GOOD", testname, testname)
        self.job.harness.run_test_complete.expect_call()
        utils.drop_caches.expect_call()

        # run and check
        self.job.run_test(testname, timeout=timeout)
        self.god.check_playback()


if __name__ == "__main__":
    unittest.main()
