#!/usr/bin/python

import os, tempfile, shutil

import common
from autotest_lib.client.common_lib import base_job
from autotest_lib.client.common_lib.test_utils import unittest


class stub_job_directory(object):
    """
    Stub job_directory class, for replacing the job._job_directory factory.
    Just creates a job_directory object without any of the actual directory
    checks. When given None it creates a temporary name (but not an actual
    temporary directory).
    """
    def __init__(self, path, is_writable=False):
        # path=None and is_writable=False is always an error
        assert path or is_writable

        if path is None and is_writable:
            self.path = tempfile.mktemp()
        else:
            self.path = path


class test_init(unittest.TestCase):
    class generic_tests(object):
        """
        Generic tests for any implementation of __init__.

        Expectations:
            A self.job attribute where self.job is a __new__'ed instance of
            the job class to be tested, but not yet __init__'ed.

            A self.call_init method that will config the appropriate mocks
            and then call job.__init__. It should undo any mocks it created
            afterwards.
        """

        PUBLIC_ATTRIBUTES = set([
            # standard directories
            'autodir', 'clientdir', 'serverdir', 'resultdir', 'pkgdir',
            'tmpdir', 'testdir', 'site_testdir', 'bindir', 'libdir',
            'configdir', 'profdir', 'toolsdir', 'conmuxdir',

            # other special attributes
            'bootloader', 'control', 'default_profile_only', 'drop_caches',
            'drop_caches_between_iterations', 'harness', 'hosts',
            'last_boot_tag', 'logging', 'machines', 'num_tests_failed',
            'num_tests_run', 'pkgmgr', 'profilers', 'resultdir',
            'run_test_cleanup', 'sysinfo', 'tag', 'user', 'warning_loggers',
            'warning_manager',
            ])

        OPTIONAL_ATTRIBUTES = set([
            'serverdir', 'conmuxdir',

            'bootloader', 'control', 'harness', 'last_boot_tag',
            'num_tests_run', 'num_tests_failed', 'tag',
            'warning_manager', 'warning_loggers',
            ])

        def test_public_attributes_initialized(self):
            # only the known public attributes should be there after __init__
            self.call_init()
            public_attributes = set(attr for attr in dir(self.job)
                                    if not attr.startswith('_')
                                    and not callable(getattr(self.job, attr)))
            expected_attributes = self.PUBLIC_ATTRIBUTES
            missing_attributes = expected_attributes - public_attributes
            self.assertEqual(missing_attributes, set([]),
                             'Missing attributes: %s' %
                             ', '.join(sorted(missing_attributes)))
            extra_attributes = public_attributes - expected_attributes
            self.assertEqual(extra_attributes, set([]),
                             'Extra public attributes found: %s' %
                             ', '.join(sorted(extra_attributes)))


        def test_required_attributes_not_none(self):
            required_attributes = (self.PUBLIC_ATTRIBUTES -
                                   self.OPTIONAL_ATTRIBUTES)
            self.call_init()
            for attribute in required_attributes:
                self.assertNotEqual(getattr(self.job, attribute, None), None,
                                    'job.%s is None but is not optional'
                                    % attribute)


class test_find_base_directories(unittest.TestCase):
    class generic_tests(object):
        """
        Generic tests for any implementation of _find_base_directories.

        Expectations:
            A self.job attribute where self.job is an instance of the job
            class to be tested.
        """
        def test_autodir_is_not_none(self):
            auto, client, server = self.job._find_base_directories()
            self.assertNotEqual(auto, None)


        def test_clientdir_is_not_none(self):
            auto, client, server = self.job._find_base_directories()
            self.assertNotEqual(client, None)


class test_initialize_dir_properties(unittest.TestCase):
    def make_job(self, autodir, server):
        job = base_job.base_job.__new__(base_job.base_job)
        job._job_directory = stub_job_directory
        job._autodir = stub_job_directory(autodir)
        if server:
            job._clientdir = stub_job_directory(
                os.path.join(autodir, 'client'))
            job._serverdir = stub_job_directory(
                os.path.join(autodir, 'server'))
        else:
            job._clientdir = stub_job_directory(job.autodir)
            job._serverdir = None
        return job


    def setUp(self):
        self.cjob = self.make_job('/atest/client', False)
        self.sjob = self.make_job('/atest', True)


    def test_always_client_dirs(self):
        self.cjob._initialize_dir_properties()
        self.sjob._initialize_dir_properties()

        # check all the always-client dir properties
        self.assertEqual(self.cjob.bindir, self.sjob.bindir)
        self.assertEqual(self.cjob.libdir, self.sjob.libdir)
        self.assertEqual(self.cjob.configdir, self.sjob.configdir)
        self.assertEqual(self.cjob.profdir, self.sjob.profdir)
        self.assertEqual(self.cjob.pkgdir, self.sjob.pkgdir)


    def test_dynamic_dirs(self):
        self.cjob._initialize_dir_properties()
        self.sjob._initialize_dir_properties()

        # check all the context-specifc dir properties
        self.assert_(self.cjob.tmpdir.startswith('/atest/client'))
        self.assert_(self.cjob.testdir.startswith('/atest/client'))
        self.assert_(self.cjob.site_testdir.startswith('/atest/client'))
        self.assert_(self.sjob.tmpdir.startswith('/atest/server'))
        self.assert_(self.sjob.testdir.startswith('/atest/server'))
        self.assert_(self.sjob.site_testdir.startswith('/atest/server'))


class test_execution_context(unittest.TestCase):
    def setUp(self):
        clientdir = os.path.abspath(os.path.join(__file__, '..', '..'))
        self.resultdir = tempfile.mkdtemp(suffix='unittest')
        self.job = base_job.base_job.__new__(base_job.base_job)
        self.job._find_base_directories = lambda: (clientdir, clientdir, None)
        self.job._find_resultdir = lambda *_: self.resultdir
        self.job.__init__()


    def tearDown(self):
        shutil.rmtree(self.resultdir, ignore_errors=True)


    def test_pop_fails_without_push(self):
        self.assertRaises(IndexError, self.job.pop_execution_context)


    def test_push_changes_to_subdir(self):
        sub1 = os.path.join(self.resultdir, 'sub1')
        os.mkdir(sub1)
        self.job.push_execution_context('sub1')
        self.assertEqual(self.job.resultdir, sub1)


    def test_push_creates_subdir(self):
        sub2 = os.path.join(self.resultdir, 'sub2')
        self.job.push_execution_context('sub2')
        self.assertEqual(self.job.resultdir, sub2)
        self.assert_(os.path.exists(sub2))


    def test_push_handles_absolute_paths(self):
        otherresults = tempfile.mkdtemp(suffix='unittest')
        try:
            self.job.push_execution_context(otherresults)
            self.assertEqual(self.job.resultdir, otherresults)
        finally:
            shutil.rmtree(otherresults, ignore_errors=True)


    def test_pop_restores_context(self):
        sub3 = os.path.join(self.resultdir, 'sub3')
        self.job.push_execution_context('sub3')
        self.assertEqual(self.job.resultdir, sub3)
        self.job.pop_execution_context()
        self.assertEqual(self.job.resultdir, self.resultdir)


    def test_push_and_pop_are_fifo(self):
        sub4 = os.path.join(self.resultdir, 'sub4')
        subsub = os.path.join(sub4, 'subsub')
        self.job.push_execution_context('sub4')
        self.assertEqual(self.job.resultdir, sub4)
        self.job.push_execution_context('subsub')
        self.assertEqual(self.job.resultdir, subsub)
        self.job.pop_execution_context()
        self.assertEqual(self.job.resultdir, sub4)
        self.job.pop_execution_context()
        self.assertEqual(self.job.resultdir, self.resultdir)


class test_job_directory(unittest.TestCase):
    def setUp(self):
        self.testdir = tempfile.mkdtemp(suffix='unittest')
        self.original_wd = os.getcwd()
        os.chdir(self.testdir)


    def tearDown(self):
        os.chdir(self.original_wd)
        shutil.rmtree(self.testdir, ignore_errors=True)


    def test_passes_if_dir_exists(self):
        os.mkdir('testing')
        self.assert_(os.path.isdir('testing'))
        jd = base_job.job_directory('testing')
        self.assert_(os.path.isdir('testing'))


    def test_fails_if_not_writable_and_dir_doesnt_exist(self):
        self.assert_(not os.path.isdir('testing2'))
        self.assertRaises(base_job.job_directory.MissingDirectoryException,
                          base_job.job_directory, 'testing2')


    def test_fails_if_file_already_exists(self):
        open('testing3', 'w').close()
        self.assert_(os.path.isfile('testing3'))
        self.assertRaises(base_job.job_directory.MissingDirectoryException,
                          base_job.job_directory, 'testing3')


    def test_passes_if_writable_and_dir_exists(self):
        os.mkdir('testing4')
        self.assert_(os.path.isdir('testing4'))
        jd = base_job.job_directory('testing4', True)
        self.assert_(os.path.isdir('testing4'))


    def test_creates_dir_if_writable_and_dir_doesnt_exist(self):
        self.assert_(not os.path.isdir('testing5'))
        jd = base_job.job_directory('testing5', True)
        self.assert_(os.path.isdir('testing5'))


    def test_recursive_creates_dir_if_writable_and_dir_doesnt_exist(self):
        self.assert_(not os.path.isdir('testing6'))
        base_job.job_directory('testing6/subdir', True)
        self.assert_(os.path.isdir('testing6/subdir'))


    def test_fails_if_writable_and_file_exists(self):
        open('testing7', 'w').close()
        self.assert_(os.path.isfile('testing7'))
        self.assert_(not os.path.isdir('testing7'))
        self.assertRaises(base_job.job_directory.UncreatableDirectoryException,
                          base_job.job_directory, 'testing7', True)


    def test_fails_if_writable_and_no_permission_to_create(self):
        os.mkdir('testing8', 0555)
        self.assert_(os.path.isdir('testing8'))
        self.assertRaises(base_job.job_directory.UncreatableDirectoryException,
                          base_job.job_directory, 'testing8/subdir', True)


    def test_passes_if_not_is_writable_and_dir_not_writable(self):
        os.mkdir('testing9', 0555)
        self.assert_(os.path.isdir('testing9'))
        self.assert_(not os.access('testing9', os.W_OK))
        jd = base_job.job_directory('testing9')


    def test_fails_if_is_writable_but_dir_not_writable(self):
        os.mkdir('testing10', 0555)
        self.assert_(os.path.isdir('testing10'))
        self.assert_(not os.access('testing10', os.W_OK))
        self.assertRaises(base_job.job_directory.UnwritableDirectoryException,
                          base_job.job_directory, 'testing10', True)


    def test_fails_if_no_path_and_not_writable(self):
        self.assertRaises(base_job.job_directory.MissingDirectoryException,
                          base_job.job_directory, None)


    def test_no_path_and_and_not_writable_creates_tempdir(self):
        jd = base_job.job_directory(None, True)
        self.assert_(os.path.isdir(jd.path))
        self.assert_(os.access(jd.path, os.W_OK))
        temp_path = jd.path
        del jd
        self.assert_(not os.path.isdir(temp_path))


if __name__ == "__main__":
    unittest.main()
