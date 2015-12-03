#!/usr/bin/python

import logging
import os
import shutil
import stat
import tempfile
import unittest

try:
    import autotest.common as common  # pylint: disable=W0611
except ImportError:
    import common  # pylint: disable=W0611
from autotest.client.shared import base_job, error
from autotest.client import job, utils


os.environ['AUTODIR'] = '/tmp/autotest'


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


class stub_job_state(base_job.job_state):

    """
    Stub job state class, for replacing the job._job_state factory.
    Doesn't actually provide any persistence, just the state handling.
    """

    def __init__(self):
        self._state = {}
        self._backing_file_lock = None

    def read_from_file(self, file_path):
        pass

    def write_to_file(self, file_path):
        pass

    def set_backing_file(self, file_path):
        pass

    def _read_from_backing_file(self):
        pass

    def _write_to_backing_file(self):
        pass

    def _lock_backing_file(self):
        pass

    def _unlock_backing_file(self):
        pass


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
            'tmpdir', 'testdir', 'site_testdir', 'bindir',
            'configdir', 'profdir', 'toolsdir', 'conmuxdir', 'customtestdir',

            # other special attributes
            'args', 'automatic_test_tag', 'bootloader', 'control',
            'default_profile_only', 'drop_caches',
            'drop_caches_between_iterations', 'harness', 'hosts',
            'last_boot_tag', 'logging', 'machines', 'num_tests_failed',
            'num_tests_run', 'pkgmgr', 'profilers', 'resultdir',
            'run_test_cleanup', 'sysinfo', 'tag', 'user', 'use_sequence_number',
            'warning_loggers', 'warning_manager',
        ])

        OPTIONAL_ATTRIBUTES = set([
            'serverdir', 'conmuxdir',

            'automatic_test_tag', 'bootloader', 'control', 'harness',
            'last_boot_tag', 'num_tests_run', 'num_tests_failed', 'tag',
            'warning_manager', 'warning_loggers',
        ])

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
        self.god.stub_function_to_return(utils, 'safe_rmdir', None)

        class manager:

            def start_logging(self):
                return None
        self.god.stub_function_to_return(job.logging_manager,
                                         'get_logging_manager', manager())

        class stub_sysinfo:

            @staticmethod
            def log_per_reboot_data():
                return None

        self.god.stub_function_to_return(job.sysinfo, 'sysinfo',
                                         stub_sysinfo())

        class stub_harness:

            @staticmethod
            def run_start():
                return None

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

        self.job._job_state = stub_job_state
        self.job.__init__('/control', options)

        def test_public_attributes_initialized(self):
            # only the known public attributes should be there after __init__
            self.call_init()
            public_attributes = set(attr for attr in dir(self.job) if
                                    not attr.startswith('_') and
                                    not callable(getattr(self.job, attr)))
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
        self.assertEqual(self.cjob.configdir, self.sjob.configdir)
        self.assertEqual(self.cjob.profdir, self.sjob.profdir)
        self.assertEqual(self.cjob.pkgdir, self.sjob.pkgdir)

    def test_dynamic_dirs(self):
        self.cjob._initialize_dir_properties()
        self.sjob._initialize_dir_properties()

        # check all the context-specifc dir properties
        self.assertTrue(self.cjob.testdir.startswith('/atest/client'))
        self.assertTrue(self.sjob.testdir.startswith('/atest/server'))


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
        if os.getuid() != 0:
            os.mkdir('testing8', 0555)
            self.assert_(os.path.isdir('testing8'))
            self.assertRaises(base_job.job_directory.UncreatableDirectoryException,
                              base_job.job_directory, 'testing8/subdir', True)

    def test_passes_if_not_is_writable_and_dir_not_writable(self):
        if os.getuid() != 0:
            os.mkdir('testing9', 0555)
            self.assert_(os.path.isdir('testing9'))
            self.assert_(not os.access('testing9', os.W_OK))
            jd = base_job.job_directory('testing9')

    def test_fails_if_is_writable_but_dir_not_writable(self):
        if os.getuid() != 0:
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


class test_job_state(unittest.TestCase):

    def setUp(self):
        self.state = base_job.job_state()

    def test_undefined_name_returns_key_error(self):
        self.assertRaises(KeyError, self.state.get, 'ns1', 'missing_name')

    def test_undefined_name_returns_default(self):
        self.assertEqual(42, self.state.get('ns2', 'missing_name', default=42))

    def test_none_is_valid_default(self):
        self.assertEqual(None, self.state.get('ns3', 'missing_name',
                                              default=None))

    def test_get_returns_set_values(self):
        self.state.set('ns4', 'name1', 50)
        self.assertEqual(50, self.state.get('ns4', 'name1'))

    def test_get_ignores_default_when_value_is_defined(self):
        self.state.set('ns5', 'name2', 55)
        self.assertEqual(55, self.state.get('ns5', 'name2', default=45))

    def test_set_only_sets_one_value(self):
        self.state.set('ns6', 'name3', 50)
        self.assertEqual(50, self.state.get('ns6', 'name3'))
        self.assertRaises(KeyError, self.state.get, 'ns6', 'name4')

    def test_set_works_with_multiple_names(self):
        self.state.set('ns7', 'name5', 60)
        self.state.set('ns7', 'name6', 70)
        self.assertEquals(60, self.state.get('ns7', 'name5'))
        self.assertEquals(70, self.state.get('ns7', 'name6'))

    def test_multiple_sets_override_each_other(self):
        self.state.set('ns8', 'name7', 10)
        self.state.set('ns8', 'name7', 25)
        self.assertEquals(25, self.state.get('ns8', 'name7'))

    def test_get_with_default_does_not_set(self):
        self.assertEquals(100, self.state.get('ns9', 'name8', default=100))
        self.assertRaises(KeyError, self.state.get, 'ns9', 'name8')

    def test_set_in_one_namespace_ignores_other(self):
        self.state.set('ns10', 'name9', 200)
        self.assertEquals(200, self.state.get('ns10', 'name9'))
        self.assertRaises(KeyError, self.state.get, 'ns11', 'name9')

    def test_namespaces_do_not_collide(self):
        self.state.set('ns12', 'name10', 250)
        self.state.set('ns13', 'name10', -150)
        self.assertEquals(-150, self.state.get('ns13', 'name10'))
        self.assertEquals(250, self.state.get('ns12', 'name10'))

    def test_discard_does_nothing_on_undefined_namespace(self):
        self.state.discard('missing_ns', 'missing')
        self.assertRaises(KeyError, self.state.get, 'missing_ns', 'missing')

    def test_discard_does_nothing_on_missing_name(self):
        self.state.set('ns14', 'name20', 111)
        self.state.discard('ns14', 'missing')
        self.assertEqual(111, self.state.get('ns14', 'name20'))
        self.assertRaises(KeyError, self.state.get, 'ns14', 'missing')

    def test_discard_deletes_name(self):
        self.state.set('ns15', 'name21', 4567)
        self.assertEqual(4567, self.state.get('ns15', 'name21'))
        self.state.discard('ns15', 'name21')
        self.assertRaises(KeyError, self.state.get, 'ns15', 'name21')

    def test_discard_doesnt_touch_other_values(self):
        self.state.set('ns16_1', 'name22', 'val1')
        self.state.set('ns16_1', 'name23', 'val2')
        self.state.set('ns16_2', 'name23', 'val3')
        self.assertEqual('val1', self.state.get('ns16_1', 'name22'))
        self.assertEqual('val3', self.state.get('ns16_2', 'name23'))
        self.state.discard('ns16_1', 'name23')
        self.assertEqual('val1', self.state.get('ns16_1', 'name22'))
        self.assertEqual('val3', self.state.get('ns16_2', 'name23'))

    def test_has_is_true_for_all_set_values(self):
        self.state.set('ns17_1', 'name24', 1)
        self.state.set('ns17_1', 'name25', 2)
        self.state.set('ns17_2', 'name25', 3)
        self.assert_(self.state.has('ns17_1', 'name24'))
        self.assert_(self.state.has('ns17_1', 'name25'))
        self.assert_(self.state.has('ns17_2', 'name25'))

    def test_has_is_false_for_all_unset_values(self):
        self.state.set('ns18_1', 'name26', 1)
        self.state.set('ns18_1', 'name27', 2)
        self.state.set('ns18_2', 'name27', 3)
        self.assert_(not self.state.has('ns18_2', 'name26'))

    def test_discard_namespace_drops_all_values(self):
        self.state.set('ns19', 'var1', 10)
        self.state.set('ns19', 'var3', 100)
        self.state.discard_namespace('ns19')
        self.assertRaises(KeyError, self.state.get, 'ns19', 'var1')
        self.assertRaises(KeyError, self.state.get, 'ns19', 'var3')

    def test_discard_namespace_works_on_missing_namespace(self):
        self.state.discard_namespace('missing_ns')

    def test_discard_namespace_doesnt_touch_other_values(self):
        self.state.set('ns20', 'var1', 20)
        self.state.set('ns20', 'var2', 200)
        self.state.set('ns21', 'var2', 21)
        self.state.discard_namespace('ns20')
        self.assertEqual(21, self.state.get('ns21', 'var2'))


# run the same tests as test_job_state, but with a backing file turned on
# also adds some tests to check that each method is persistent
class test_job_state_with_backing_file(test_job_state):

    def setUp(self):
        self.backing_file = tempfile.mktemp()
        self.state = base_job.job_state()
        self.state.set_backing_file(self.backing_file)

    def tearDown(self):
        if os.path.exists(self.backing_file):
            os.remove(self.backing_file)

    def test_set_is_persistent(self):
        self.state.set('persist', 'var', 'value')
        written_state = base_job.job_state()
        written_state.read_from_file(self.backing_file)
        self.assertEqual('value', written_state.get('persist', 'var'))

    def test_discard_is_persistent(self):
        self.state.set('persist', 'var', 'value')
        self.state.discard('persist', 'var')
        written_state = base_job.job_state()
        written_state.read_from_file(self.backing_file)
        self.assertRaises(KeyError, written_state.get, 'persist', 'var')

    def test_discard_namespace_is_persistent(self):
        self.state.set('persist', 'var', 'value')
        self.state.discard_namespace('persist')
        written_state = base_job.job_state()
        written_state.read_from_file(self.backing_file)
        self.assertRaises(KeyError, written_state.get, 'persist', 'var')


class test_job_state_read_write_file(unittest.TestCase):

    def setUp(self):
        self.testdir = tempfile.mkdtemp(suffix='unittest')
        self.original_wd = os.getcwd()
        os.chdir(self.testdir)

    def tearDown(self):
        os.chdir(self.original_wd)
        shutil.rmtree(self.testdir, ignore_errors=True)

    def test_write_read_transfers_all_state(self):
        state1 = base_job.job_state()
        state1.set('ns1', 'var0', 50)
        state1.set('ns2', 'var10', 100)
        state1.write_to_file('transfer_file')
        state2 = base_job.job_state()
        self.assertRaises(KeyError, state2.get, 'ns1', 'var0')
        self.assertRaises(KeyError, state2.get, 'ns2', 'var10')
        state2.read_from_file('transfer_file')
        self.assertEqual(50, state2.get('ns1', 'var0'))
        self.assertEqual(100, state2.get('ns2', 'var10'))

    def test_read_overwrites_in_memory(self):
        state = base_job.job_state()
        state.set('ns', 'myvar', 'hello')
        state.write_to_file('backup')
        state.set('ns', 'myvar', 'goodbye')
        self.assertEqual('goodbye', state.get('ns', 'myvar'))
        state.read_from_file('backup')
        self.assertEqual('hello', state.get('ns', 'myvar'))

    def test_read_updates_persistent_file(self):
        state1 = base_job.job_state()
        state1.set('ns', 'var1', 'value1')
        state1.write_to_file('to_be_read')
        state2 = base_job.job_state()
        state2.set_backing_file('backing_file')
        state2.set('ns', 'var2', 'value2')
        state2.read_from_file('to_be_read')
        state2.set_backing_file(None)
        state3 = base_job.job_state()
        state3.read_from_file('backing_file')
        self.assertEqual('value1', state3.get('ns', 'var1'))
        self.assertEqual('value2', state3.get('ns', 'var2'))

    def test_read_without_merge(self):
        state = base_job.job_state()
        state.set('ns', 'myvar1', 'hello')
        state.write_to_file('backup')
        state.discard('ns', 'myvar1')
        state.set('ns', 'myvar2', 'goodbye')
        self.assertFalse(state.has('ns', 'myvar1'))
        self.assertEqual('goodbye', state.get('ns', 'myvar2'))
        state.read_from_file('backup', merge=False)
        self.assertEqual('hello', state.get('ns', 'myvar1'))
        self.assertFalse(state.has('ns', 'myvar2'))


class test_job_state_set_backing_file(unittest.TestCase):

    def setUp(self):
        self.testdir = tempfile.mkdtemp(suffix='unittest')
        self.original_wd = os.getcwd()
        os.chdir(self.testdir)

    def tearDown(self):
        os.chdir(self.original_wd)
        shutil.rmtree(self.testdir, ignore_errors=True)

    def test_writes_to_file(self):
        state = base_job.job_state()
        state.set_backing_file('outfile1')
        self.assert_(os.path.exists('outfile1'))

    def test_set_backing_file_updates_existing_file(self):
        state1 = base_job.job_state()
        state1.set_backing_file('second_file')
        state1.set('ns0', 'var1x', 100)
        state1.set_backing_file(None)
        state2 = base_job.job_state()
        state2.set_backing_file('first_file')
        state2.set('ns0', 'var0x', 0)
        state2.set_backing_file('second_file')
        state2.set_backing_file(None)
        state3 = base_job.job_state()
        state3.read_from_file('second_file')
        self.assertEqual(0, state3.get('ns0', 'var0x'))
        self.assertEqual(100, state3.get('ns0', 'var1x'))

    def test_set_backing_file_does_not_overwrite_previous_backing_file(self):
        state1 = base_job.job_state()
        state1.set_backing_file('second_file')
        state1.set('ns0', 'var1y', 10)
        state1.set_backing_file(None)
        state2 = base_job.job_state()
        state2.set_backing_file('first_file')
        state2.set('ns0', 'var0y', -10)
        state2.set_backing_file('second_file')
        state2.set_backing_file(None)
        state3 = base_job.job_state()
        state3.read_from_file('first_file')
        self.assertEqual(-10, state3.get('ns0', 'var0y'))
        self.assertRaises(KeyError, state3.get, 'ns0', 'var1y')

    def test_writes_stop_after_backing_file_removed(self):
        state = base_job.job_state()
        state.set('ns', 'var1', 'value1')
        state.set_backing_file('outfile2')
        state.set_backing_file(None)
        os.remove('outfile2')
        state.set('n2', 'var2', 'value2')
        self.assert_(not os.path.exists('outfile2'))

    def test_written_files_can_be_reloaded(self):
        state1 = base_job.job_state()
        state1.set_backing_file('outfile3')
        state1.set('n3', 'var1', 67)
        state1.set_backing_file(None)
        state2 = base_job.job_state()
        self.assertRaises(KeyError, state2.get, 'n3', 'var1')
        state2.set_backing_file('outfile3')
        self.assertEqual(67, state2.get('n3', 'var1'))

    def test_backing_file_overrides_in_memory_values(self):
        state1 = base_job.job_state()
        state1.set_backing_file('outfile4')
        state1.set('n4', 'var1', 42)
        state1.set_backing_file(None)
        state2 = base_job.job_state()
        state2.set('n4', 'var1', 430)
        self.assertEqual(430, state2.get('n4', 'var1'))
        state2.set_backing_file('outfile4')
        self.assertEqual(42, state2.get('n4', 'var1'))

    def test_backing_file_only_overrides_values_it_defines(self):
        state1 = base_job.job_state()
        state1.set_backing_file('outfile5')
        state1.set('n5', 'var1', 123)
        state1.set_backing_file(None)
        state2 = base_job.job_state()
        state2.set('n5', 'var2', 456)
        state2.set_backing_file('outfile5')
        self.assertEqual(123, state2.get('n5', 'var1'))
        self.assertEqual(456, state2.get('n5', 'var2'))

    def test_shared_backing_file_propagates_state_to_get(self):
        state1 = base_job.job_state()
        state1.set_backing_file('outfile6')
        state2 = base_job.job_state()
        state2.set_backing_file('outfile6')
        self.assertRaises(KeyError, state1.get, 'n6', 'shared1')
        self.assertRaises(KeyError, state2.get, 'n6', 'shared1')
        state1.set('n6', 'shared1', 345)
        self.assertEqual(345, state1.get('n6', 'shared1'))
        self.assertEqual(345, state2.get('n6', 'shared1'))

    def test_shared_backing_file_propagates_state_to_has(self):
        state1 = base_job.job_state()
        state1.set_backing_file('outfile7')
        state2 = base_job.job_state()
        state2.set_backing_file('outfile7')
        self.assertFalse(state1.has('n6', 'shared2'))
        self.assertFalse(state2.has('n6', 'shared2'))
        state1.set('n6', 'shared2', 'hello')
        self.assertTrue(state1.has('n6', 'shared2'))
        self.assertTrue(state2.has('n6', 'shared2'))

    def test_shared_backing_file_propagates_state_from_discard(self):
        state1 = base_job.job_state()
        state1.set_backing_file('outfile8')
        state1.set('n6', 'shared3', 10000)
        state2 = base_job.job_state()
        state2.set_backing_file('outfile8')
        self.assertEqual(10000, state1.get('n6', 'shared3'))
        self.assertEqual(10000, state2.get('n6', 'shared3'))
        state1.discard('n6', 'shared3')
        self.assertRaises(KeyError, state1.get, 'n6', 'shared3')
        self.assertRaises(KeyError, state2.get, 'n6', 'shared3')

    def test_shared_backing_file_propagates_state_from_discard_namespace(self):
        state1 = base_job.job_state()
        state1.set_backing_file('outfile9')
        state1.set('n7', 'shared4', -1)
        state1.set('n7', 'shared5', -2)
        state2 = base_job.job_state()
        state2.set_backing_file('outfile9')
        self.assertEqual(-1, state1.get('n7', 'shared4'))
        self.assertEqual(-1, state2.get('n7', 'shared4'))
        self.assertEqual(-2, state1.get('n7', 'shared5'))
        self.assertEqual(-2, state2.get('n7', 'shared5'))
        state1.discard_namespace('n7')
        self.assertRaises(KeyError, state1.get, 'n7', 'shared4')
        self.assertRaises(KeyError, state2.get, 'n7', 'shared4')
        self.assertRaises(KeyError, state1.get, 'n7', 'shared5')
        self.assertRaises(KeyError, state2.get, 'n7', 'shared5')


class test_job_state_backing_file_locking(unittest.TestCase):

    def setUp(self):
        self.testdir = tempfile.mkdtemp(suffix='unittest')
        self.original_wd = os.getcwd()
        os.chdir(self.testdir)

        # create a job_state object with stub read_* and write_* methods
        # to check that a lock is always held during a call to them
        ut_self = self

        class mocked_job_state(base_job.job_state):

            def read_from_file(self, file_path, merge=True):
                if self._backing_file and file_path == self._backing_file:
                    ut_self.assertNotEqual(None, self._backing_file_lock)
                # pylint: disable=E1003
                return super(mocked_job_state, self).read_from_file(
                    file_path, merge=True)

            def write_to_file(self, file_path):
                if self._backing_file and file_path == self._backing_file:
                    ut_self.assertNotEqual(None, self._backing_file_lock)
                # pylint: disable=E1003
                return super(mocked_job_state, self).write_to_file(file_path)
        self.state = mocked_job_state()
        self.state.set_backing_file('backing_file')

    def tearDown(self):
        os.chdir(self.original_wd)
        shutil.rmtree(self.testdir, ignore_errors=True)

    def test_set(self):
        self.state.set('ns1', 'var1', 100)

    def test_get_missing(self):
        self.assertRaises(KeyError, self.state.get, 'ns2', 'var2')

    def test_get_present(self):
        self.state.set('ns3', 'var3', 333)
        self.assertEqual(333, self.state.get('ns3', 'var3'))

    def test_set_backing_file(self):
        self.state.set_backing_file('some_other_file')

    def test_has_missing(self):
        self.assertFalse(self.state.has('ns4', 'var4'))

    def test_has_present(self):
        self.state.set('ns5', 'var5', 55555)
        self.assertTrue(self.state.has('ns5', 'var5'))

    def test_discard_missing(self):
        self.state.discard('ns6', 'var6')

    def test_discard_present(self):
        self.state.set('ns7', 'var7', -777)
        self.state.discard('ns7', 'var7')

    def test_discard_missing_namespace(self):
        self.state.discard_namespace('ns8')

    def test_discard_present_namespace(self):
        self.state.set('ns8', 'var8', 80)
        self.state.set('ns8', 'var8.1', 81)
        self.state.discard_namespace('ns8')

    def test_disable_backing_file(self):
        self.state.set_backing_file(None)

    def test_change_backing_file(self):
        self.state.set_backing_file('another_backing_file')

    def test_read_from_a_non_backing_file(self):
        state = base_job.job_state()
        state.set('ns9', 'var9', 9999)
        state.write_to_file('non_backing_file')
        self.state.read_from_file('non_backing_file')

    def test_write_to_a_non_backing_file(self):
        self.state.write_to_file('non_backing_file')


class test_job_state_property_factory(unittest.TestCase):

    def setUp(self):
        class job_stub(object):
            pass
        self.job_class = job_stub
        self.job = job_stub()
        self.state = base_job.job_state()
        self.job.stateobj = self.state

    def test_properties_are_readwrite(self):
        self.job_class.testprop1 = base_job.job_state.property_factory(
            'stateobj', 'testprop1', 1)
        self.job.testprop1 = 'testvalue'
        self.assertEqual('testvalue', self.job.testprop1)

    def test_properties_use_default_if_not_initialized(self):
        self.job_class.testprop2 = base_job.job_state.property_factory(
            'stateobj', 'testprop2', 'abc123')
        self.assertEqual('abc123', self.job.testprop2)

    def test_properties_do_not_collisde(self):
        self.job_class.testprop3 = base_job.job_state.property_factory(
            'stateobj', 'testprop3', 2)
        self.job_class.testprop4 = base_job.job_state.property_factory(
            'stateobj', 'testprop4', 3)
        self.job.testprop3 = 500
        self.job.testprop4 = '1000'
        self.assertEqual(500, self.job.testprop3)
        self.assertEqual('1000', self.job.testprop4)

    def test_properties_do_not_collide_across_different_state_objects(self):
        self.job_class.testprop5 = base_job.job_state.property_factory(
            'stateobj', 'testprop5', 55)
        self.job.auxstateobj = base_job.job_state()
        self.job_class.auxtestprop5 = base_job.job_state.property_factory(
            'auxstateobj', 'testprop5', 600)
        self.job.auxtestprop5 = 700
        self.assertEqual(55, self.job.testprop5)
        self.assertEqual(700, self.job.auxtestprop5)

    def test_properties_do_not_collide_across_different_job_objects(self):
        self.job_class.testprop6 = base_job.job_state.property_factory(
            'stateobj', 'testprop6', 'defaultval')
        job1 = self.job
        job2 = self.job_class()
        job2.stateobj = base_job.job_state()
        job1.testprop6 = 'notdefaultval'
        self.assertEqual('notdefaultval', job1.testprop6)
        self.assertEqual('defaultval', job2.testprop6)
        job2.testprop6 = 'job2val'
        self.assertEqual('notdefaultval', job1.testprop6)
        self.assertEqual('job2val', job2.testprop6)

    def test_properties_in_different_namespaces_do_not_collide(self):
        self.job_class.ns1 = base_job.job_state.property_factory(
            'stateobj', 'attribute', 'default1', namespace='ns1')
        self.job_class.ns2 = base_job.job_state.property_factory(
            'stateobj', 'attribute', 'default2', namespace='ns2')
        self.assertEqual('default1', self.job.ns1)
        self.assertEqual('default2', self.job.ns2)
        self.job.ns1 = 'notdefault'
        self.job.ns2 = 'alsonotdefault'
        self.assertEqual('notdefault', self.job.ns1)
        self.assertEqual('alsonotdefault', self.job.ns2)


class test_status_log_entry(unittest.TestCase):

    def test_accepts_valid_status_code(self):
        base_job.status_log_entry('GOOD', None, None, '', None)
        base_job.status_log_entry('FAIL', None, None, '', None)
        base_job.status_log_entry('ABORT', None, None, '', None)

    def test_accepts_valid_start_status_code(self):
        base_job.status_log_entry('START', None, None, '', None)

    def test_accepts_valid_end_status_code(self):
        base_job.status_log_entry('END GOOD', None, None, '', None)
        base_job.status_log_entry('END FAIL', None, None, '', None)
        base_job.status_log_entry('END ABORT', None, None, '', None)

    def test_rejects_invalid_status_code(self):
        self.assertRaises(ValueError, base_job.status_log_entry,
                          'FAKE', None, None, '', None)

    def test_rejects_invalid_start_status_code(self):
        self.assertRaises(ValueError, base_job.status_log_entry,
                          'START GOOD', None, None, '', None)
        self.assertRaises(ValueError, base_job.status_log_entry,
                          'START FAIL', None, None, '', None)
        self.assertRaises(ValueError, base_job.status_log_entry,
                          'START ABORT', None, None, '', None)
        self.assertRaises(ValueError, base_job.status_log_entry,
                          'START FAKE', None, None, '', None)

    def test_rejects_invalid_end_status_code(self):
        self.assertRaises(ValueError, base_job.status_log_entry,
                          'END FAKE', None, None, '', None)

    def test_accepts_valid_subdir(self):
        base_job.status_log_entry('GOOD', 'subdir', None, '', None)
        base_job.status_log_entry('FAIL', 'good.subdir', None, '', None)

    def test_rejects_bad_subdir(self):
        self.assertRaises(ValueError, base_job.status_log_entry,
                          'GOOD', 'bad.subdir\t', None, '', None)
        self.assertRaises(ValueError, base_job.status_log_entry,
                          'GOOD', 'bad.subdir\t', None, '', None)
        self.assertRaises(ValueError, base_job.status_log_entry,
                          'GOOD', 'bad.subdir\t', None, '', None)
        self.assertRaises(ValueError, base_job.status_log_entry,
                          'GOOD', 'bad.subdir\t', None, '', None)
        self.assertRaises(ValueError, base_job.status_log_entry,
                          'GOOD', 'bad.subdir\t', None, '', None)

    def test_accepts_valid_operation(self):
        base_job.status_log_entry('GOOD', None, 'build', '', None)
        base_job.status_log_entry('FAIL', None, 'clean', '', None)

    def test_rejects_bad_operation(self):
        self.assertRaises(ValueError, base_job.status_log_entry,
                          'GOOD', None, 'bad.operation\n', '', None)
        self.assertRaises(ValueError, base_job.status_log_entry,
                          'GOOD', None, 'bad.\voperation', '', None)
        self.assertRaises(ValueError, base_job.status_log_entry,
                          'GOOD', None, 'bad.\foperation', '', None)
        self.assertRaises(ValueError, base_job.status_log_entry,
                          'GOOD', None, 'bad\r.operation', '', None)
        self.assertRaises(ValueError, base_job.status_log_entry,
                          'GOOD', None, '\tbad.operation', '', None)

    def test_simple_message(self):
        base_job.status_log_entry('ERROR', None, None, 'simple error message',
                                  None)

    def test_message_split_into_multiple_lines(self):
        def make_entry(msg):
            return base_job.status_log_entry('GOOD', None, None, msg, None)
        base_job.status_log_entry('ABORT', None, None, 'first line\nsecond',
                                  None)

    def test_message_with_tabs(self):
        base_job.status_log_entry('GOOD', None, None, '\tindent\tagain', None)

    def test_message_with_custom_fields(self):
        base_job.status_log_entry('GOOD', None, None, 'my message',
                                  {'key1': 'blah', 'key2': 'blahblah'})

    def assertRendered(self, rendered, status, subdir, operation, msg,
                       extra_fields, timestamp):
        parts = rendered.split('\t')
        self.assertEqual(parts[0], status)
        self.assertEqual(parts[1], subdir)
        self.assertEqual(parts[2], operation)
        self.assertEqual(parts[-1], msg)
        fields = dict(f.split('=', 1) for f in parts[3:-1])
        self.assertEqual(int(fields['timestamp']), timestamp)
        self.assert_('localtime' in fields)  # too flaky to do an exact check
        del fields['timestamp']
        del fields['localtime']
        self.assertEqual(fields, extra_fields)

    def test_base_render(self):
        entry = base_job.status_log_entry('GOOD', None, None, 'message1', None,
                                          timestamp=1)
        self.assertRendered(entry.render(), 'GOOD', '----', '----', 'message1',
                            {}, 1)

    def test_subdir_render(self):
        entry = base_job.status_log_entry('FAIL', 'sub', None, 'message2', None,
                                          timestamp=2)
        self.assertRendered(entry.render(), 'FAIL', 'sub', '----', 'message2',
                            {}, 2)

    def test_operation_render(self):
        entry = base_job.status_log_entry('ABORT', None, 'myop', 'message3',
                                          None, timestamp=4)
        self.assertRendered(entry.render(), 'ABORT', '----', 'myop', 'message3',
                            {}, 4)

    def test_fields_render(self):
        custom_fields = {'custom1': 'foo', 'custom2': 'bar'}
        entry = base_job.status_log_entry('WARN', None, None, 'message4',
                                          custom_fields, timestamp=8)
        self.assertRendered(entry.render(), 'WARN', '----', '----', 'message4',
                            custom_fields, 8)

    def assertEntryEqual(self, lhs, rhs):
        self.assertEqual(
            (lhs.status_code, lhs.subdir, lhs.operation, lhs.fields, lhs.message),
            (rhs.status_code, rhs.subdir, rhs.operation, rhs.fields, rhs.message))

    def test_base_parse(self):
        entry = base_job.status_log_entry(
            'GOOD', None, None, 'message', {'field1': 'x', 'field2': 'y'},
            timestamp=16)
        parsed_entry = base_job.status_log_entry.parse(
            'GOOD\t----\t----\tfield1=x\tfield2=y\ttimestamp=16\tmessage\n')
        self.assertEntryEqual(entry, parsed_entry)

    def test_subdir_parse(self):
        entry = base_job.status_log_entry(
            'FAIL', 'sub', None, 'message', {'field1': 'x', 'field2': 'y'},
            timestamp=32)
        parsed_entry = base_job.status_log_entry.parse(
            'FAIL\tsub\t----\tfield1=x\tfield2=y\ttimestamp=32\tmessage\n')
        self.assertEntryEqual(entry, parsed_entry)

    def test_operation_parse(self):
        entry = base_job.status_log_entry(
            'ABORT', None, 'myop', 'message', {'field1': 'x', 'field2': 'y'},
            timestamp=64)
        parsed_entry = base_job.status_log_entry.parse(
            'ABORT\t----\tmyop\tfield1=x\tfield2=y\ttimestamp=64\tmessage\n')
        self.assertEntryEqual(entry, parsed_entry)

    def test_extra_lines_parse(self):
        parsed_entry = base_job.status_log_entry.parse(
            '  This is a non-status line, line in a traceback\n')
        self.assertEqual(None, parsed_entry)


class test_status_logger(unittest.TestCase):

    def setUp(self):
        self.testdir = tempfile.mkdtemp(suffix='unittest')
        self.original_wd = os.getcwd()
        os.chdir(self.testdir)

        class stub_job(object):
            resultdir = self.testdir
        self.job = stub_job()  # need to hold a reference to the job

        class stub_indenter(object):

            def __init__(self):
                self.indent = 0

            def increment(self):
                self.indent += 1

            def decrement(self):
                self.indent -= 1
        self.indenter = stub_indenter()
        self.logger = base_job.status_logger(self.job, self.indenter)

    def make_dummy_entry(self, rendered_text, start=False, end=False,
                         subdir=None):
        """Helper to make a dummy status log entry with custom rendered text.

        Helpful when validating the logging since it lets the test control
        the rendered text and so it doesn't depend on the exact formatting
        of a "real" status log entry.

        :param rendred_text: The value to return when rendering the entry.
        :param start: An optional value indicating if this should be the start
            of a nested group.
        :param end: An optional value indicating if this should be the end
            of a nested group.
        :param subdir: An optional value to use for the entry subdir field.

        :return: A dummy status log entry object with the given subdir field
            and a render implementation that returns rendered_text.
        """
        assert not start or not end  # real entries would never be both

        class dummy_entry(object):

            def is_start(self):
                return start

            def is_end(self):
                return end

            def render(self):
                return rendered_text
        entry = dummy_entry()
        entry.subdir = subdir
        return entry

    def test_render_includes_indent(self):
        entry = self.make_dummy_entry('LINE0')
        self.assertEqual('LINE0', self.logger.render_entry(entry))
        self.indenter.increment()
        self.indenter.increment()
        self.assertEqual('\t\tLINE0', self.logger.render_entry(entry))

    def test_render_handles_start(self):
        entry = self.make_dummy_entry('LINE10', start=True)
        self.indenter.increment()
        self.assertEqual('\tLINE10', self.logger.render_entry(entry))

    def test_render_handles_end(self):
        entry = self.make_dummy_entry('LINE20', end=True)
        self.indenter.increment()
        self.indenter.increment()
        self.indenter.increment()
        self.assertEqual('\t\tLINE20', self.logger.render_entry(entry))

    def test_writes_toplevel_log(self):
        entries = [self.make_dummy_entry('LINE%d' % x) for x in xrange(3)]
        for entry in entries:
            self.logger.record_entry(entry)
        self.assertEqual('LINE0\nLINE1\nLINE2\n', open('status').read())

    def test_uses_given_filenames(self):
        os.mkdir('sub')
        self.logger = base_job.status_logger(self.job, self.indenter,
                                             global_filename='global.log',
                                             subdir_filename='subdir.log')
        self.logger.record_entry(self.make_dummy_entry('LINE1', subdir='sub'))
        self.logger.record_entry(self.make_dummy_entry('LINE2', subdir='sub'))
        self.logger.record_entry(self.make_dummy_entry('LINE3'))

        self.assertEqual('LINE1\nLINE2\nLINE3\n', open('global.log').read())
        self.assertEqual('LINE1\nLINE2\n', open('sub/subdir.log').read())

        self.assertFalse(os.path.exists('status'))
        self.assertFalse(os.path.exists('sub/status'))
        self.assertFalse(os.path.exists('subdir.log'))
        self.assertFalse(os.path.exists('sub/global.log'))

    def test_filenames_are_mutable(self):
        os.mkdir('sub2')
        self.logger = base_job.status_logger(self.job, self.indenter,
                                             global_filename='global.log',
                                             subdir_filename='subdir.log')
        self.logger.record_entry(self.make_dummy_entry('LINE1', subdir='sub2'))
        self.logger.record_entry(self.make_dummy_entry('LINE2'))
        self.logger.global_filename = 'global.log2'
        self.logger.subdir_filename = 'subdir.log2'
        self.logger.record_entry(self.make_dummy_entry('LINE3', subdir='sub2'))
        self.logger.record_entry(self.make_dummy_entry('LINE4'))

        self.assertEqual('LINE1\nLINE2\n', open('global.log').read())
        self.assertEqual('LINE1\n', open('sub2/subdir.log').read())
        self.assertEqual('LINE3\nLINE4\n', open('global.log2').read())
        self.assertEqual('LINE3\n', open('sub2/subdir.log2').read())

    def test_writes_subdir_logs(self):
        os.mkdir('abc')
        os.mkdir('123')
        self.logger.record_entry(self.make_dummy_entry('LINE1'))
        self.logger.record_entry(self.make_dummy_entry('LINE2', subdir='abc'))
        self.logger.record_entry(self.make_dummy_entry('LINE3', subdir='abc'))
        self.logger.record_entry(self.make_dummy_entry('LINE4', subdir='123'))

        self.assertEqual('LINE1\nLINE2\nLINE3\nLINE4\n', open('status').read())
        self.assertEqual('LINE2\nLINE3\n', open('abc/status').read())
        self.assertEqual('LINE4\n', open('123/status').read())

    def test_writes_no_subdir_when_disabled(self):
        os.mkdir('sub')
        self.logger.record_entry(self.make_dummy_entry('LINE1'))
        self.logger.record_entry(self.make_dummy_entry('LINE2', subdir='sub'))
        self.logger.record_entry(self.make_dummy_entry(
            'LINE3', subdir='sub_nowrite'), log_in_subdir=False)
        self.logger.record_entry(self.make_dummy_entry('LINE4', subdir='sub'))

        self.assertEqual('LINE1\nLINE2\nLINE3\nLINE4\n', open('status').read())
        self.assertEqual('LINE2\nLINE4\n', open('sub/status').read())
        self.assert_(not os.path.exists('sub_nowrite/status'))

    def test_indentation(self):
        self.logger.record_entry(self.make_dummy_entry('LINE1', start=True))
        self.logger.record_entry(self.make_dummy_entry('LINE2'))
        self.logger.record_entry(self.make_dummy_entry('LINE3', start=True))
        self.logger.record_entry(self.make_dummy_entry('LINE4'))
        self.logger.record_entry(self.make_dummy_entry('LINE5'))
        self.logger.record_entry(self.make_dummy_entry('LINE6', end=True))
        self.logger.record_entry(self.make_dummy_entry('LINE7', end=True))
        self.logger.record_entry(self.make_dummy_entry('LINE8'))

        expected_log = ('LINE1\n\tLINE2\n\tLINE3\n\t\tLINE4\n\t\tLINE5\n'
                        '\tLINE6\nLINE7\nLINE8\n')
        self.assertEqual(expected_log, open('status').read())

    def test_multiline_indent(self):
        self.logger.record_entry(self.make_dummy_entry('LINE1\n  blah\n'))
        self.logger.record_entry(self.make_dummy_entry('LINE2', start=True))
        self.logger.record_entry(
            self.make_dummy_entry('LINE3\n  blah\n  two\n'))
        self.logger.record_entry(self.make_dummy_entry('LINE4', end=True))

        expected_log = ('LINE1\n  blah\nLINE2\n'
                        '\tLINE3\n  blah\n  two\nLINE4\n')
        self.assertEqual(expected_log, open('status').read())

    def test_hook_is_called(self):
        entries = [self.make_dummy_entry('LINE%d' % x) for x in xrange(5)]
        recorded_entries = []

        def hook(entry):
            recorded_entries.append(entry)
        self.logger = base_job.status_logger(self.job, self.indenter,
                                             record_hook=hook)
        for entry in entries:
            self.logger.record_entry(entry)
        self.assertEqual(entries, recorded_entries)

    def tearDown(self):
        os.chdir(self.original_wd)
        shutil.rmtree(self.testdir, ignore_errors=True)


class test_job_tags(unittest.TestCase):

    def setUp(self):
        class stub_job(base_job.base_job):
            _job_directory = stub_job_directory

            @classmethod
            # pylint: disable=E0202
            def _find_base_directories(cls):
                return '/autodir', '/autodir/client', '/autodir/server'
            # pylint: disable=E0202

            def _find_resultdir(self):
                return '/autodir/results'
        self.job = stub_job()

    def test_default_with_no_args_means_no_tags(self):
        self.assertEqual(('testname', 'testname', ''),
                         self.job._build_tagged_test_name('testname', {}))
        self.assertEqual(('othername', 'othername', ''),
                         self.job._build_tagged_test_name('othername', {}))

    def test_tag_argument_appended(self):
        self.assertEqual(
            ('test1.mytag', 'test1.mytag', 'mytag'),
            self.job._build_tagged_test_name('test1', {'tag': 'mytag'}))

    def test_turning_on_use_sequence_adds_sequence_tags(self):
        self.job.use_sequence_number = True
        self.assertEqual(
            ('test2._01_', 'test2._01_', '_01_'),
            self.job._build_tagged_test_name('test2', {}))
        self.assertEqual(
            ('test2._02_', 'test2._02_', '_02_'),
            self.job._build_tagged_test_name('test2', {}))
        self.assertEqual(
            ('test3._03_', 'test3._03_', '_03_'),
            self.job._build_tagged_test_name('test3', {}))

    def test_adding_automatic_test_tag_automatically_tags(self):
        self.job.automatic_test_tag = 'autotag'
        self.assertEqual(
            ('test4.autotag', 'test4.autotag', 'autotag'),
            self.job._build_tagged_test_name('test4', {}))

    def test_none_automatic_test_tag_turns_off_tagging(self):
        self.job.automatic_test_tag = 'autotag'
        self.assertEqual(
            ('test5.autotag', 'test5.autotag', 'autotag'),
            self.job._build_tagged_test_name('test5', {}))
        self.job.automatic_test_tag = None
        self.assertEqual(
            ('test5', 'test5', ''),
            self.job._build_tagged_test_name('test5', {}))

    def test_empty_automatic_test_tag_turns_off_tagging(self):
        self.job.automatic_test_tag = 'autotag'
        self.assertEqual(
            ('test6.autotag', 'test6.autotag', 'autotag'),
            self.job._build_tagged_test_name('test6', {}))
        self.job.automatic_test_tag = ''
        self.assertEqual(
            ('test6', 'test6', ''),
            self.job._build_tagged_test_name('test6', {}))

    def test_subdir_tag_modifies_subdir_and_tag_only(self):
        self.assertEqual(
            ('test7', 'test7.subdirtag', 'subdirtag'),
            self.job._build_tagged_test_name('test7',
                                             {'subdir_tag': 'subdirtag'}))

    def test_all_tag_components_together(self):
        self.job.use_sequence_number = True
        self.job.automatic_test_tag = 'auto'
        expected = ('test8.tag._01_.auto',
                    'test8.tag._01_.auto.subdir',
                    'tag._01_.auto.subdir')
        actual = self.job._build_tagged_test_name(
            'test8', {'tag': 'tag', 'subdir_tag': 'subdir'})
        self.assertEqual(expected, actual)

    def test_subtest_with_master_test_path_and_subdir(self):
        self.assertEqual(
            ('test9', 'subtestdir/test9.subdirtag', 'subdirtag'),
            self.job._build_tagged_test_name('test9',
                                             {'master_testpath': 'subtestdir',
                                              'subdir_tag': 'subdirtag'}))

    def test_subtest_all_tag_components_together_subdir(self):
        self.job.use_sequence_number = True
        self.job.automatic_test_tag = 'auto'
        expected = ('test10.tag._01_.auto',
                    'subtestdir/test10.tag._01_.auto.subdir',
                    'tag._01_.auto.subdir')
        actual = self.job._build_tagged_test_name(
            'test10', {'tag': 'tag', 'subdir_tag': 'subdir',
                       'master_testpath': 'subtestdir'})
        self.assertEqual(expected, actual)


class test_make_outputdir(unittest.TestCase):

    def setUp(self):
        self.resultdir = tempfile.mkdtemp(suffix='unittest')

        class stub_job(base_job.base_job):

            @classmethod
            # pylint: disable=E0202
            def _find_base_directories(cls):
                return '/autodir', '/autodir/client', '/autodir/server'

            @classmethod
            # pylint: disable=E0202
            def _find_resultdir(cls):
                return self.resultdir

        # stub out _job_directory for creation only
        stub_job._job_directory = stub_job_directory
        self.job = stub_job()
        del stub_job._job_directory

        # stub out logging.exception
        self.original_exception = logging.exception
        logging.exception = lambda *args, **dargs: None

        self.original_wd = os.getcwd()
        os.chdir(self.resultdir)

    def tearDown(self):
        logging.exception = self.original_exception
        os.chdir(self.original_wd)
        shutil.rmtree(self.resultdir, ignore_errors=True)

    def test_raises_test_error_if_outputdir_exists(self):
        os.mkdir('subdir1')
        self.assert_(os.path.exists('subdir1'))
        self.assertRaises(error.TestError, self.job._make_test_outputdir,
                          'subdir1')

    def test_raises_test_error_if_outputdir_uncreatable(self):
        if os.getuid() != 0:
            os.chmod(self.resultdir, stat.S_IRUSR | stat.S_IXUSR)
            self.assert_(not os.path.exists('subdir2'))
            self.assertRaises(OSError, os.mkdir, 'subdir2')
            self.assertRaises(error.TestError, self.job._make_test_outputdir,
                              'subdir2')
            self.assert_(not os.path.exists('subdir2'))

    def test_creates_writable_directory(self):
        self.assert_(not os.path.exists('subdir3'))
        self.job._make_test_outputdir('subdir3')
        self.assert_(os.path.isdir('subdir3'))

        # we can write to the directory afterwards
        self.assert_(not os.path.exists('subdir3/testfile'))
        open('subdir3/testfile', 'w').close()
        self.assert_(os.path.isfile('subdir3/testfile'))


if __name__ == "__main__":
    unittest.main()
