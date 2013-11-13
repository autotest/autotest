#!/usr/bin/python

import logging
import os
import shutil
import sys
import StringIO
import unittest

try:
    import autotest.common as common
except ImportError:
    import common

from autotest.client import job, setup_job
from autotest.client import utils
from autotest.client.shared import base_job, logging_manager, logging_config
from autotest.client.shared import base_job_unittest
from autotest.client.shared.test_utils import mock


class setup_job_test_case(unittest.TestCase):

    """Generic job TestCase class that defines a standard job setUp and
    tearDown, with some standard stubs."""

    job_class = setup_job.setup_job

    def setUp(self):
        self.god = mock.mock_god()
        self.god.stub_with(setup_job.setup_job, '_get_environ_autodir',
                           classmethod(lambda cls: '/adir'))
        self.job = self.job_class.__new__(self.job_class)
        self.job._job_directory = base_job_unittest.stub_job_directory
        self.job.args = []

    def tearDown(self):
        self.god.unstub_all()


class test_find_base_directories(
        base_job_unittest.test_find_base_directories.generic_tests,
        setup_job_test_case):

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
    PUBLIC_ATTRIBUTES = (
        base_job_unittest.test_init.generic_tests.PUBLIC_ATTRIBUTES
        - set(['bootloader', 'control', 'drop_caches',
               'drop_caches_between_iterations', 'harness', 'hosts', 'logging',
               'machines', 'num_tests_failed', 'num_tests_run', 'profilers',
               'sysinfo', 'user', 'warning_loggers', 'warning_manager']))


class test_init_minimal_options(abstract_test_init, setup_job_test_case):

    def call_init(self):
        # TODO(jadmanski): refactor more of the __init__ code to not need to
        # stub out countless random APIs
        self.god.stub_function_to_return(setup_job.os, 'mkdir', None)
        self.god.stub_function_to_return(setup_job.os.path, 'exists', True)
        self.god.stub_function_to_return(utils, 'safe_rmdir', None)
        self.god.stub_function_to_return(self.job, '_load_state', None)
        self.god.stub_function_to_return(logging_manager,
                                         'configure_logging', None)

        class manager:

            def start_logging(self):
                return None
        self.god.stub_function_to_return(logging_manager,
                                         'get_logging_manager', manager())

        class options:
            tag = ''
            verbose = False
            cont = False
            harness = 'stub'
            hostname = None
            user = None
            log = False
            tap_report = None
            output_dir = ''

        self.job.__init__(options)


class dummy(object):

    """A simple placeholder for attributes"""
    pass


class first_line_comparator(mock.argument_comparator):

    def __init__(self, first_line):
        self.first_line = first_line

    def is_satisfied_by(self, parameter):
        return self.first_line == parameter.splitlines()[0]


class test_setup_job(unittest.TestCase):

    def setUp(self):
        # make god
        self.god = mock.mock_god()

        # need to set some environ variables
        self.autodir = "autodir"
        os.environ['AUTODIR'] = self.autodir

        # set up some variables
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
        self.god.stub_function(setup_job, 'open')
        self.god.stub_function(utils, 'system')

        self.god.stub_class_method(job.base_client_job,
                                   '_cleanup_debugdir_files')
        self.god.stub_class_method(job.base_client_job, '_cleanup_results_dir')

        self.god.stub_with(base_job.job_directory, '_ensure_valid',
                           lambda *_: None)

    def tearDown(self):
        sys.stdout = sys.__stdout__
        self.god.unstub_all()

    def _setup_pre_record_init(self):
        resultdir = os.path.join(self.autodir, 'results', self.jobtag)
        tmpdir = os.path.join(self.autodir, 'tmp')
        job.base_client_job._cleanup_debugdir_files.expect_call()
        job.base_client_job._cleanup_results_dir.expect_call()

        return resultdir

    def construct_job(self):
        # will construct class instance using __new__
        self.job = setup_job.setup_job.__new__(setup_job.setup_job)

        resultdir = self._setup_pre_record_init()

        # finish constructor
        options = dummy()
        options.tag = self.jobtag
        options.log = False
        options.verbose = False
        options.hostname = 'localhost'
        options.user = 'my_user'
        options.tap_report = None
        options.output_dir = ''
        self.job.__init__(options)

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
        self.construct_job()

    def test_constructor_continuation(self):
        self.construct_job()

    def test_relative_path(self):
        self.construct_job()
        dummy = "asdf"
        ret = self.job.relative_path(os.path.join(self.job.resultdir, dummy))
        self.assertEquals(ret, dummy)

    def test_setup_dirs_raise(self):
        self.construct_job()

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
        self.construct_job()

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


if __name__ == "__main__":
    unittest.main()
