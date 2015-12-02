#!/usr/bin/python

import os
import re
import unittest
try:
    import autotest.common as common  # pylint: disable=W0611
except ImportError:
    import common  # pylint: disable=W0611
from autotest.frontend import setup_django_environment  # pylint: disable=W0611
from autotest.frontend import setup_test_environment  # pylint: disable=W0611
from autotest.client.shared.test_utils import mock
from django.db import connection
from autotest.frontend.tko import models, rpc_interface

# this will need to be updated if the table schemas change (or removed if we
# add proper primary keys)
_CREATE_ITERATION_ATTRIBUTES = """
CREATE TABLE tko_iteration_attributes (
    test_idx integer NOT NULL REFERENCES tko_tests (test_idx),
    iteration integer NOT NULL,
    attribute varchar(90) NOT NULL,
    value varchar(300) NOT NULL
);
"""

_CREATE_ITERATION_RESULTS = """
CREATE TABLE tko_iteration_result (
    test_idx integer NOT NULL REFERENCES tko_tests (test_idx),
    iteration integer NOT NULL,
    attribute varchar(90) NOT NULL,
    value numeric(31, 12) NULL
);
"""


def get_create_test_view_sql():
    """
    Returns the SQL code that creates the test view
    """
    dir_path = os.path.dirname(os.path.abspath(__file__))
    sql_path = os.path.join(dir_path, 'sql', 'tko-test-view-2.sql')
    return open(sql_path).read()


def setup_test_view():
    """
    Django has no way to actually represent a view; we simply create a model for
    TestView. So manually create the view.
    """
    cursor = connection.cursor()
    cursor.execute('DROP VIEW IF EXISTS tko_test_view_2')
    cursor.execute(get_create_test_view_sql())


def fix_iteration_tables():
    """
    Since iteration tables don't have any real primary key, we "fake" one in the
    Django models.  So fix up the generated schema to match the real schema.
    """
    cursor = connection.cursor()
    cursor.execute('DROP TABLE tko_iteration_attributes')
    cursor.execute(_CREATE_ITERATION_ATTRIBUTES)
    cursor.execute('DROP TABLE tko_iteration_result')
    cursor.execute(_CREATE_ITERATION_RESULTS)


class TkoTestMixin(object):

    def _patch_sqlite_stuff(self):
        self.god.stub_with(models.TempManager, '_get_column_names',
                           self._get_column_names_for_sqlite3)
        self.god.stub_with(models.TempManager, '_cursor_rowcount',
                           self._cursor_rowcount_for_sqlite3)

        connection.cursor()  # ensure connection is alive
        # add some functions to SQLite for MySQL compatibility
        if hasattr(connection.connection, "create_function"):
            connection.connection.create_function('if', 3, self._sqlite_if)
            connection.connection.create_function('find_in_set', 2,
                                                  self._sqlite_find_in_set)

        fix_iteration_tables()

    def _cursor_rowcount_for_sqlite3(self, cursor):
        return len(cursor.fetchall())

    def _sqlite_find_in_set(self, needle, haystack):
        return needle in haystack.split(',')

    def _sqlite_if(self, condition, true_result, false_result):
        if condition:
            return true_result
        return false_result

    # sqlite takes any columns that don't have aliases and names them
    # "table_name"."column_name".  we map these to just column_name.
    _SQLITE_AUTO_COLUMN_ALIAS_RE = re.compile(r'".+"\."(.+)"')

    def _get_column_names_for_sqlite3(self, cursor):
        names = [column_info[0] for column_info in cursor.description]

        # replace all "table_name"."column_name" constructs with just
        # column_name
        for i, name in enumerate(names):
            match = self._SQLITE_AUTO_COLUMN_ALIAS_RE.match(name)
            if match:
                names[i] = match.group(1)

        return names

    def _create_initial_data(self):
        machine = models.Machine.objects.create(hostname='myhost')

        # create basic objects
        kernel_name = 'mykernel1'
        kernel1 = models.Kernel.objects.create(kernel_hash=kernel_name,
                                               base=kernel_name,
                                               printable=kernel_name)

        kernel_name = 'mykernel2'
        kernel2 = models.Kernel.objects.create(kernel_hash=kernel_name,
                                               base=kernel_name,
                                               printable=kernel_name)

        good_status = models.Status.objects.create(word='GOOD')
        failed_status = models.Status.objects.create(word='FAILED')

        job1 = models.Job.objects.create(tag='1-myjobtag1', label='myjob1',
                                         username='myuser', machine=machine,
                                         afe_job_id=1)
        job2 = models.Job.objects.create(tag='2-myjobtag2', label='myjob2',
                                         username='myuser', machine=machine,
                                         afe_job_id=2)

        job1_test1 = models.Test.objects.create(job=job1, test='mytest1',
                                                kernel=kernel1,
                                                status=good_status,
                                                machine=machine)
        self.first_test = job1_test1
        job1_test2 = models.Test.objects.create(job=job1, test='mytest2',
                                                kernel=kernel1,
                                                status=failed_status,
                                                machine=machine)
        job2_test1 = models.Test.objects.create(job=job2, test='kernbench',
                                                kernel=kernel2,
                                                status=good_status,
                                                machine=machine)

        job1.jobkeyval_set.create(key='keyval_key', value='keyval_value')

        # create test attributes, test labels, and iterations
        # like Noah's Ark, include two of each...just in case there's a bug with
        # multiple related items
        models.TestAttribute.objects.create(test=job1_test1, attribute='myattr',
                                            value='myval')
        models.TestAttribute.objects.create(test=job1_test1,
                                            attribute='myattr2', value='myval2')

        self._add_iteration_keyval('tko_iteration_attributes', test=job1_test1,
                                   iteration=1, attribute='iattr',
                                   value='ival')
        self._add_iteration_keyval('tko_iteration_attributes', test=job1_test1,
                                   iteration=1, attribute='iattr2',
                                   value='ival2')
        self._add_iteration_keyval('tko_iteration_result', test=job1_test1,
                                   iteration=1, attribute='iresult', value=1)
        self._add_iteration_keyval('tko_iteration_result', test=job1_test1,
                                   iteration=1, attribute='iresult2', value=2)
        self._add_iteration_keyval('tko_iteration_result', test=job1_test1,
                                   iteration=2, attribute='iresult', value=3)
        self._add_iteration_keyval('tko_iteration_result', test=job1_test1,
                                   iteration=2, attribute='iresult2', value=4)

        # With the new database initialization based on Django, the fixture
        # file is always loaded. That file has one entry, so the labels
        # created for the test have ids set to 2 and 3, and not 1 and 2. We
        # name them like this so that is even more explicit
        label2 = models.TestLabel.objects.create(name='testlabel2')
        label3 = models.TestLabel.objects.create(name='testlabel3')

        label2.tests.add(job1_test1)
        label3.tests.add(job1_test1)

    def _add_iteration_keyval(self, table, test, iteration, attribute, value):
        cursor = connection.cursor()
        cursor.execute('INSERT INTO %s ' 'VALUES (%%s, %%s, %%s, %%s)' % table,
                       (test.test_idx, iteration, attribute, value))


class RpcInterfaceTest(unittest.TestCase, TkoTestMixin):

    def setUp(self):
        self.god = mock.mock_god()

        setup_test_environment.set_up()
        self._patch_sqlite_stuff()
        setup_test_view()
        self._create_initial_data()

    def tearDown(self):
        setup_test_environment.tear_down()
        self.god.unstub_all()

    def _check_for_get_test_views(self, test):
        self.assertEquals(test['test_name'], 'mytest1')
        self.assertEquals(test['job_tag'], '1-myjobtag1')
        self.assertEquals(test['job_name'], 'myjob1')
        self.assertEquals(test['job_owner'], 'myuser')
        self.assertEquals(test['status'], 'GOOD')
        self.assertEquals(test['hostname'], 'myhost')
        self.assertEquals(test['kernel'], 'mykernel1')

    def test_get_detailed_test_views(self):
        test = rpc_interface.get_detailed_test_views()[0]

        self._check_for_get_test_views(test)

        self.assertEquals(test['attributes'], {'myattr': 'myval',
                                               'myattr2': 'myval2'})
        self.assertEquals(test['iterations'], [{'attr': {'iattr': 'ival',
                                                         'iattr2': 'ival2'},
                                                'perf': {'iresult': 1,
                                                         'iresult2': 2}},
                                               {'attr': {},
                                                'perf': {'iresult': 3,
                                                         'iresult2': 4}}])
        self.assertEquals(test['labels'], ['testlabel2', 'testlabel3'])
        self.assertEquals(test['job_keyvals'], {'keyval_key': 'keyval_value'})

    def test_test_attributes(self):
        rpc_interface.set_test_attribute('foo', 'bar', test_name='mytest1')
        test = rpc_interface.get_detailed_test_views()[0]
        self.assertEquals(test['attributes'], {'foo': 'bar',
                                               'myattr': 'myval',
                                               'myattr2': 'myval2'})

        rpc_interface.set_test_attribute('foo', 'goo', test_name='mytest1')
        test = rpc_interface.get_detailed_test_views()[0]
        self.assertEquals(test['attributes'], {'foo': 'goo',
                                               'myattr': 'myval',
                                               'myattr2': 'myval2'})

        rpc_interface.set_test_attribute('foo', None, test_name='mytest1')
        test = rpc_interface.get_detailed_test_views()[0]
        self.assertEquals(test['attributes'], {'myattr': 'myval',
                                               'myattr2': 'myval2'})

    def test_immutable_attributes(self):
        self.assertRaises(ValueError, rpc_interface.set_test_attribute,
                          'myattr', 'foo', test_name='mytest1')

    def test_get_test_views(self):
        tests = rpc_interface.get_test_views()

        self.assertEquals(len(tests), 3)
        test = rpc_interface.get_test_views(
            job_name='myjob1', test_name='mytest1')[0]
        self.assertEquals(tests[0], test)

        self._check_for_get_test_views(test)

        self.assertEquals(
            [], rpc_interface.get_test_views(hostname='fakehost'))

    def _check_test_names(self, tests, expected_names):
        self.assertEquals(set(test['test_name'] for test in tests),
                          set(expected_names))

    def test_get_test_views_filter_on_labels(self):
        tests = rpc_interface.get_test_views(include_labels=['testlabel2'])
        self._check_test_names(tests, ['mytest1'])

        tests = rpc_interface.get_test_views(exclude_labels=['testlabel2'])
        self._check_test_names(tests, ['mytest2', 'kernbench'])

    def test_get_test_views_filter_on_attributes(self):
        tests = rpc_interface.get_test_views(
            include_attributes_where='attribute = "myattr" '
            'and value = "myval"')
        self._check_test_names(tests, ['mytest1'])

        tests = rpc_interface.get_test_views(
            exclude_attributes_where='attribute="myattr2"')
        self._check_test_names(tests, ['mytest2', 'kernbench'])

    def test_get_num_test_views(self):
        self.assertEquals(rpc_interface.get_num_test_views(), 3)
        self.assertEquals(rpc_interface.get_num_test_views(
            job_name='myjob1', test_name='mytest1'), 1)

    def test_get_group_counts(self):
        self.assertEquals(rpc_interface.get_num_groups(['job_name']), 2)

        counts = rpc_interface.get_group_counts(['job_name'])
        groups = counts['groups']
        self.assertEquals(len(groups), 2)
        group1, group2 = groups

        self.assertEquals(group1['group_count'], 2)
        self.assertEquals(group1['job_name'], 'myjob1')
        self.assertEquals(group2['group_count'], 1)
        self.assertEquals(group2['job_name'], 'myjob2')

        extra = {'extra': 'kernel_hash'}
        counts = rpc_interface.get_group_counts(['job_name'],
                                                header_groups=[('job_name',)],
                                                extra_select_fields=extra)
        groups = counts['groups']
        self.assertEquals(len(groups), 2)
        group1, group2 = groups

        self.assertEquals(group1['group_count'], 2)
        self.assertEquals(group1['header_indices'], [0])
        self.assertEquals(group1['extra'], 'mykernel1')
        self.assertEquals(group2['group_count'], 1)
        self.assertEquals(group2['header_indices'], [1])
        self.assertEquals(group2['extra'], 'mykernel2')

    def test_get_status_counts(self):
        counts = rpc_interface.get_status_counts(group_by=['job_name'])
        group1, group2 = counts['groups']
        self.assertEquals(group1['pass_count'], 1)
        self.assertEquals(group1['complete_count'], 2)
        self.assertEquals(group1['incomplete_count'], 0)
        self.assertEquals(group2['pass_count'], 1)
        self.assertEquals(group2['complete_count'], 1)
        self.assertEquals(group2['incomplete_count'], 0)

    def test_get_latest_tests(self):
        counts = rpc_interface.get_latest_tests(group_by=['job_name'])
        group1, group2 = counts['groups']
        self.assertEquals(group1['pass_count'], 0)
        self.assertEquals(group1['complete_count'], 1)
        self.assertEquals(group1['test_idx'], 2)
        self.assertEquals(group2['test_idx'], 3)

    def test_get_latest_tests_extra_info(self):
        counts = rpc_interface.get_latest_tests(group_by=['job_name'],
                                                extra_info=['job_tag'])
        group1, group2 = counts['groups']
        self.assertEquals(group1['extra_info'], ['1-myjobtag1'])
        self.assertEquals(group2['extra_info'], ['2-myjobtag2'])

    def test_get_job_ids(self):
        self.assertEquals([1, 2], rpc_interface.get_job_ids())
        self.assertEquals([1], rpc_interface.get_job_ids(test_name='mytest2'))

    def test_get_hosts_and_tests(self):
        host_info = rpc_interface.get_hosts_and_tests()
        self.assertEquals(len(host_info), 1)
        info = host_info['myhost']

        self.assertEquals(info['tests'], ['kernbench'])
        self.assertEquals(info['id'], 1)

    def _check_for_get_test_labels(self, label, label_num):
        self.assertEquals(label['id'], label_num)
        self.assertEquals(label['description'], '')
        self.assertEquals(label['name'], 'testlabel%d' % label_num)

    def test_test_labels(self):
        labels = rpc_interface.get_test_labels_for_tests(test_name='mytest1')
        self.assertEquals(len(labels), 2)
        label2 = labels[0]
        label3 = labels[1]

        self._check_for_get_test_labels(label2, 2)
        self._check_for_get_test_labels(label3, 3)

        rpc_interface.test_label_remove_tests(label2['id'], test_name='mytest1')

        labels = rpc_interface.get_test_labels_for_tests(test_name='mytest1')
        self.assertEquals(len(labels), 1)
        label = labels[0]

        self._check_for_get_test_labels(label, 3)

        rpc_interface.test_label_add_tests(label2['id'], test_name='mytest1')

        labels = rpc_interface.get_test_labels_for_tests(test_name='mytest1')
        self.assertEquals(len(labels), 2)
        label2 = labels[0]
        label3 = labels[1]

        self._check_for_get_test_labels(label2, 2)
        self._check_for_get_test_labels(label3, 3)

    def test_get_test_attribute_fields(self):
        tests = rpc_interface.get_test_views(
            test_attribute_fields=['myattr', 'myattr2'])
        self.assertEquals(len(tests), 3)

        self.assertEquals(tests[0]['test_attribute_myattr'], 'myval')
        self.assertEquals(tests[0]['test_attribute_myattr2'], 'myval2')

        for index in (1, 2):
            self.assertEquals(tests[index]['test_attribute_myattr'], None)
            self.assertEquals(tests[index]['test_attribute_myattr2'], None)

    def test_filtering_on_test_attribute_fields(self):
        tests = rpc_interface.get_test_views(
            extra_where='test_attribute_myattr.value = "myval"',
            test_attribute_fields=['myattr'])
        self.assertEquals(len(tests), 1)

    def test_grouping_with_test_attribute_fields(self):
        num_groups = rpc_interface.get_num_groups(
            ['test_attribute_myattr'], test_attribute_fields=['myattr'])
        self.assertEquals(num_groups, 2)

        counts = rpc_interface.get_group_counts(
            ['test_attribute_myattr'], test_attribute_fields=['myattr'])
        groups = counts['groups']
        self.assertEquals(len(groups), num_groups)
        self.assertEquals(groups[0]['test_attribute_myattr'], None)
        self.assertEquals(groups[0]['group_count'], 2)
        self.assertEquals(groups[1]['test_attribute_myattr'], 'myval')
        self.assertEquals(groups[1]['group_count'], 1)

    def test_extra_info_test_attributes(self):
        counts = rpc_interface.get_latest_tests(
            group_by=['test_idx'], extra_info=['test_attribute_myattr'],
            test_attribute_fields=['myattr'])
        group1 = counts['groups'][0]
        self.assertEquals(group1['extra_info'], ['myval'])

    def test_get_test_label_fields(self):
        tests = rpc_interface.get_test_views(
            test_label_fields=['testlabel2', 'testlabel3'])
        self.assertEquals(len(tests), 3)

        self.assertEquals(tests[0]['test_label_testlabel2'], 'testlabel2')
        self.assertEquals(tests[0]['test_label_testlabel3'], 'testlabel3')

        for index in (1, 2):
            self.assertEquals(tests[index]['test_label_testlabel2'], None)
            self.assertEquals(tests[index]['test_label_testlabel3'], None)

    def test_filtering_on_test_label_fields(self):
        tests = rpc_interface.get_test_views(
            extra_where='test_label_testlabel2 = "testlabel2"',
            test_label_fields=['testlabel2'])
        self.assertEquals(len(tests), 1)

    def test_grouping_on_test_label_fields(self):
        num_groups = rpc_interface.get_num_groups(
            ['test_label_testlabel2'], test_label_fields=['testlabel2'])
        self.assertEquals(num_groups, 2)

        counts = rpc_interface.get_group_counts(
            ['test_label_testlabel2'], test_label_fields=['testlabel2'])
        groups = counts['groups']
        self.assertEquals(len(groups), 2)
        self.assertEquals(groups[0]['test_label_testlabel2'], None)
        self.assertEquals(groups[0]['group_count'], 2)
        self.assertEquals(groups[1]['test_label_testlabel2'], 'testlabel2')
        self.assertEquals(groups[1]['group_count'], 1)

    def test_get_iteration_result_fields(self):
        num_iterations = rpc_interface.get_num_test_views(
            iteration_result_fields=['iresult', 'iresult2'])
        self.assertEquals(num_iterations, 2)

        iterations = rpc_interface.get_test_views(
            iteration_result_fields=['iresult', 'iresult2'])
        self.assertEquals(len(iterations), 2)

        for index in (0, 1):
            self.assertEquals(iterations[index]['test_idx'], 1)

        self.assertEquals(iterations[0]['iteration_index'], 1)
        self.assertEquals(iterations[0]['iteration_result_iresult'], 1)
        self.assertEquals(iterations[0]['iteration_result_iresult2'], 2)

        self.assertEquals(iterations[1]['iteration_index'], 2)
        self.assertEquals(iterations[1]['iteration_result_iresult'], 3)
        self.assertEquals(iterations[1]['iteration_result_iresult2'], 4)

    def test_filtering_on_iteration_result_fields(self):
        iterations = rpc_interface.get_test_views(
            extra_where='iteration_result_iresult.value = 1',
            iteration_result_fields=['iresult'])
        self.assertEquals(len(iterations), 1)

    def test_grouping_with_iteration_result_fields(self):
        num_groups = rpc_interface.get_num_groups(
            ['iteration_result_iresult'],
            iteration_result_fields=['iresult'])
        self.assertEquals(num_groups, 2)

        counts = rpc_interface.get_group_counts(
            ['iteration_result_iresult'],
            iteration_result_fields=['iresult'])
        groups = counts['groups']
        self.assertEquals(len(groups), 2)
        self.assertEquals(groups[0]['iteration_result_iresult'], 1)
        self.assertEquals(groups[0]['group_count'], 1)
        self.assertEquals(groups[1]['iteration_result_iresult'], 3)
        self.assertEquals(groups[1]['group_count'], 1)

    def _setup_machine_labels(self):
        models.TestAttribute.objects.create(test=self.first_test,
                                            attribute='host-labels',
                                            value='label1,label2')

    def test_get_machine_label_fields(self):
        self._setup_machine_labels()

        tests = rpc_interface.get_test_views(
            machine_label_fields=['label1', 'otherlabel'])
        self.assertEquals(len(tests), 3)

        self.assertEquals(tests[0]['machine_label_label1'], 'label1')
        self.assertEquals(tests[0]['machine_label_otherlabel'], None)

        for index in (1, 2):
            self.assertEquals(tests[index]['machine_label_label1'], None)
            self.assertEquals(tests[index]['machine_label_otherlabel'], None)

    def test_grouping_with_machine_label_fields(self):
        self._setup_machine_labels()

        counts = rpc_interface.get_group_counts(['machine_label_label1'],
                                                machine_label_fields=['label1'])
        groups = counts['groups']
        self.assertEquals(len(groups), 2)
        self.assertEquals(groups[0]['machine_label_label1'], None)
        self.assertEquals(groups[0]['group_count'], 2)
        self.assertEquals(groups[1]['machine_label_label1'], 'label1')
        self.assertEquals(groups[1]['group_count'], 1)

    def test_filtering_on_machine_label_fields(self):
        self._setup_machine_labels()

        tests = rpc_interface.get_test_views(
            extra_where='machine_label_label1 = "label1"',
            machine_label_fields=['label1'])
        self.assertEquals(len(tests), 1)

    def test_quoting_fields(self):
        # ensure fields with special characters are properly quoted throughout
        rpc_interface.add_test_label('hyphen-label')
        rpc_interface.get_group_counts(
            ['test_attribute_hyphen-attr', 'test_label_hyphen-label',
             'machine_label_hyphen-label',
             'iteration_result_hyphen-result'],
            test_attribute_fields=['hyphen-attr'],
            test_label_fields=['hyphen-label'],
            machine_label_fields=['hyphen-label'],
            iteration_result_fields=['hyphen-result'])


if __name__ == '__main__':
    unittest.main()
