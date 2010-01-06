#!/usr/bin/python

import os, stat, tempfile, shutil, logging

import common
from autotest_lib.client.common_lib import base_job, error
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
            'tmpdir', 'testdir', 'site_testdir', 'bindir',
            'configdir', 'profdir', 'toolsdir', 'conmuxdir',

            # other special attributes
            'automatic_test_tag', 'bootloader', 'control',
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


    def test_read_missing_file_is_nop(self):
        self.assert_(not os.path.exists('doesnotexist'))
        state = base_job.job_state()
        state.set('namespace', 'var', 'val1')
        state.set('namespace2', 'var', 'val2')
        state.write_to_file('initial')
        state.read_from_file('doesnotexist')
        state.write_to_file('final')
        self.assertEqual(open('initial').read(), open('final').read())


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


class test_job_tags(unittest.TestCase):
    def setUp(self):
        class stub_job(base_job.base_job):
            _job_directory = stub_job_directory
            @classmethod
            def _find_base_directories(cls):
                return '/autodir', '/autodir/client', '/autodir/server'
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


class test_make_outputdir(unittest.TestCase):
    def setUp(self):
        self.resultdir = tempfile.mkdtemp(suffix='unittest')
        class stub_job(base_job.base_job):
            @classmethod
            def _find_base_directories(cls):
                return '/autodir', '/autodir/client', '/autodir/server'
            def _find_resultdir(inner_self):
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
