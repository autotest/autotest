#!/usr/bin/python

import unittest
import common
from autotest_lib.new_tko import setup_django_environment
from autotest_lib.frontend import setup_test_environment
from autotest_lib.client.common_lib.test_utils import mock
from django.db import connection
from autotest_lib.new_tko.tko import models, rpc_interface

# this will need to be updated when the view changes for the test to be
# consistent with reality
_CREATE_TEST_VIEW = """
CREATE VIEW test_view_2 AS
SELECT  tests.test_idx AS test_idx,
        tests.job_idx AS job_idx,
        tests.test AS test_name,
        tests.subdir AS subdir,
        tests.kernel_idx AS kernel_idx,
        tests.status AS status_idx,
        tests.reason AS reason,
        tests.machine_idx AS machine_idx,
        tests.started_time AS test_started_time,
        tests.finished_time AS test_finished_time,
        jobs.tag AS job_tag,
        jobs.label AS job_name,
        jobs.username AS job_owner,
        jobs.queued_time AS job_queued_time,
        jobs.started_time AS job_started_time,
        jobs.finished_time AS job_finished_time,
        jobs.afe_job_id AS afe_job_id,
        machines.hostname AS hostname,
        machines.machine_group AS platform,
        machines.owner AS machine_owner,
        kernels.kernel_hash AS kernel_hash,
        kernels.base AS kernel_base,
        kernels.printable AS kernel,
        status.word AS status
FROM tests
INNER JOIN jobs ON jobs.job_idx = tests.job_idx
INNER JOIN machines ON machines.machine_idx = jobs.machine_idx
INNER JOIN kernels ON kernels.kernel_idx = tests.kernel_idx
INNER JOIN status ON status.status_idx = tests.status;
"""

# this will need to be updated if the table schemas change (or removed if we
# add proper primary keys)
_CREATE_ITERATION_ATTRIBUTES = """
CREATE TABLE "iteration_attributes" (
    "test_idx" integer NOT NULL REFERENCES "tests" ("test_idx"),
    "iteration" integer NOT NULL,
    "attribute" varchar(90) NOT NULL,
    "value" varchar(300) NOT NULL
);
"""

_CREATE_ITERATION_RESULTS = """
CREATE TABLE "iteration_result" (
    "test_idx" integer NOT NULL REFERENCES "tests" ("test_idx"),
    "iteration" integer NOT NULL,
    "attribute" varchar(90) NOT NULL,
    "value" numeric(12, 31) NULL
);
"""


def setup_test_view():
    """
    Django has no way to actually represent a view; we simply create a model for
    TestView.   This means when we syncdb, Django will create a table for it.
    So manually remove that table and replace it with a view.
    """
    cursor = connection.cursor()
    cursor.execute('DROP TABLE test_view_2')
    cursor.execute(_CREATE_TEST_VIEW)


def fix_iteration_tables():
    """
    Since iteration tables don't have any real primary key, we "fake" one in the
    Django models.  So fix up the generated schema to match the real schema.
    """
    cursor = connection.cursor()
    cursor.execute('DROP TABLE iteration_attributes')
    cursor.execute(_CREATE_ITERATION_ATTRIBUTES)
    cursor.execute('DROP TABLE iteration_result')
    cursor.execute(_CREATE_ITERATION_RESULTS)


class RpcInterfaceTest(unittest.TestCase):
    def setUp(self):
        self._god = mock.mock_god()
        setup_test_environment.set_up()
        fix_iteration_tables()
        setup_test_view()
        self._create_initial_data()


    def tearDown(self):
        setup_test_environment.tear_down()
        self._god.unstub_all()


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
                                         username='myuser', machine=machine)
        job2 = models.Job.objects.create(tag='2-myjobtag2', label='myjob2',
                                         username='myuser', machine=machine)

        job1_test1 = models.Test.objects.create(job=job1, test='mytest1',
                                                kernel=kernel1,
                                                status=good_status,
                                                machine=machine)
        job1_test2 = models.Test.objects.create(job=job1, test='mytest2',
                                                kernel=kernel1,
                                                status=failed_status,
                                                machine=machine)
        job2_test1 = models.Test.objects.create(job=job2, test='kernbench',
                                                kernel=kernel2,
                                                status=good_status,
                                                machine=machine)

        # create test attributes, test labels, and iterations
        # like Noah's Ark, include two of each...just in case there's a bug with
        # multiple related items
        models.TestAttribute.objects.create(test=job1_test1, attribute='myattr',
                                            value='myval')
        models.TestAttribute.objects.create(test=job1_test1,
                                            attribute='myattr2', value='myval2')

        self._add_iteration_keyval('iteration_attributes', test=job1_test1,
                                   iteration=1, attribute='iattr',
                                   value='ival')
        self._add_iteration_keyval('iteration_attributes', test=job1_test1,
                                   iteration=1, attribute='iattr2',
                                   value='ival2')
        self._add_iteration_keyval('iteration_result', test=job1_test1,
                                   iteration=1, attribute='iresult', value=1)
        self._add_iteration_keyval('iteration_result', test=job1_test1,
                                   iteration=1, attribute='iresult2', value=2)
        self._add_iteration_keyval('iteration_result', test=job1_test1,
                                   iteration=2, attribute='iresult', value=3)
        self._add_iteration_keyval('iteration_result', test=job1_test1,
                                   iteration=2, attribute='iresult2', value=4)

        label1 = models.TestLabel.objects.create(name='testlabel1')
        label2 = models.TestLabel.objects.create(name='testlabel2')

        label1.tests.add(job1_test1)
        label2.tests.add(job1_test1)


    def _add_iteration_keyval(self, table, test, iteration, attribute, value):
        cursor = connection.cursor()
        cursor.execute('INSERT INTO %s ' 'VALUES (%%s, %%s, %%s, %%s)' % table,
                       (test.test_idx, iteration, attribute, value))


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
        self.assertEquals(test['labels'], ['testlabel1', 'testlabel2'])


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
        tests = rpc_interface.get_test_views(include_labels=['testlabel1'])
        self._check_test_names(tests, ['mytest1'])

        tests = rpc_interface.get_test_views(exclude_labels=['testlabel1'])
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


    def _get_column_names_for_sqlite3(self, cursor):
        names = [column_info[0] for column_info in cursor.description]

        # replace all "table_name"."column_name" constructs with just
        # column_name
        for i, name in enumerate(names):
            if '.' in name:
                field_name = name.split('.', 1)[1]
                names[i] = field_name.strip('"')

        return names


    def test_get_group_counts(self):
        self._god.stub_with(models.TempManager, '_get_column_names',
                            self._get_column_names_for_sqlite3)

        self.assertEquals(rpc_interface.get_num_groups(['job_name']), 2)

        counts = rpc_interface.get_group_counts(['job_name'])
        groups = counts['groups']
        self.assertEquals(len(groups), 2)
        group1 = groups[0]
        group2 = groups[1]

        self.assertEquals(group1['group_count'], 2)
        self.assertEquals(group1['job_name'], 'myjob1')
        self.assertEquals(group2['group_count'], 1)
        self.assertEquals(group2['job_name'], 'myjob2')

        extra = {'extra' : 'kernel_hash'}
        counts = rpc_interface.get_group_counts(['job_name'],
                                                header_groups=[('job_name',)],
                                                extra_select_fields=extra)
        groups = counts['groups']
        self.assertEquals(len(groups), 2)
        group1 = groups[0]
        group2 = groups[1]

        self.assertEquals(group1['group_count'], 2)
        self.assertEquals(group1['header_indices'], [0])
        self.assertEquals(group1['extra'], 'mykernel1')
        self.assertEquals(group2['group_count'], 1)
        self.assertEquals(group2['header_indices'], [1])
        self.assertEquals(group2['extra'], 'mykernel2')


    def test_get_status_counts(self):
        """\
        This method cannot be tested with a sqlite3 test framework. The method
        relies on the IF function, which is not present in sqlite3.
        """


    def test_get_latest_tests(self):
        """\
        This method cannot be tested with a sqlite3 test framework. The method
        relies on the IF function, which is not present in sqlite3.
        """


    def test_get_job_ids(self):
        self.assertEquals([1,2], rpc_interface.get_job_ids())
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
        label1 = labels[0]
        label2 = labels[1]

        self._check_for_get_test_labels(label1, 1)
        self._check_for_get_test_labels(label2, 2)

        rpc_interface.test_label_remove_tests(label1['id'], test_name='mytest1')

        labels = rpc_interface.get_test_labels_for_tests(test_name='mytest1')
        self.assertEquals(len(labels), 1)
        label = labels[0]

        self._check_for_get_test_labels(label, 2)

        rpc_interface.test_label_add_tests(label1['id'], test_name='mytest1')

        labels = rpc_interface.get_test_labels_for_tests(test_name='mytest1')
        self.assertEquals(len(labels), 2)
        label1 = labels[0]
        label2 = labels[1]

        self._check_for_get_test_labels(label1, 1)
        self._check_for_get_test_labels(label2, 2)


    def test_get_iteration_views(self):
        iterations = rpc_interface.get_iteration_views(['iresult', 'iresult2'],
                                                       job_name='myjob1',
                                                       test_name='mytest1')
        self.assertEquals(len(iterations), 2)
        for index, iteration in enumerate(iterations):
            self._check_for_get_test_views(iterations[index])
            # iterations a one-indexed, not zero-indexed
            self.assertEquals(iteration['iteration_index'], index + 1)

        self.assertEquals(iterations[0]['iresult'], 1)
        self.assertEquals(iterations[0]['iresult2'], 2)
        self.assertEquals(iterations[1]['iresult'], 3)
        self.assertEquals(iterations[1]['iresult2'], 4)

        self.assertEquals(
                [], rpc_interface.get_iteration_views(['iresult'],
                                                      hostname='fakehost'))
        self.assertEquals(
                [], rpc_interface.get_iteration_views(['fake']))


    def test_get_num_iteration_views(self):
        self.assertEquals(
                rpc_interface.get_num_iteration_views(['iresult', 'iresult2']),
                2)
        self.assertEquals(rpc_interface.get_num_iteration_views(['fake']), 0)


if __name__ == '__main__':
    unittest.main()
