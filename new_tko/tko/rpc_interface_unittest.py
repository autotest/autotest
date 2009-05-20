#!/usr/bin/python2.4

import unittest
import common
from autotest_lib.new_tko import setup_django_environment
from autotest_lib.frontend import setup_test_environment
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
        setup_test_environment.set_up()
        fix_iteration_tables()
        setup_test_view()
        self._create_initial_data()


    def tearDown(self):
        setup_test_environment.tear_down()


    def _create_initial_data(self):
        machine = models.Machine(hostname='host1')
        machine.save()

        kernel_name = 'mykernel'
        kernel = models.Kernel(kernel_hash=kernel_name, base=kernel_name,
                               printable=kernel_name)
        kernel.save()

        status = models.Status(word='GOOD')
        status.save()

        job = models.Job(tag='myjobtag', label='myjob', username='myuser',
                         machine=machine)
        job.save()

        test = models.Test(job=job, test='mytest', kernel=kernel,
                                status=status, machine=machine)
        test.save()

        # like Noah's Ark, include two of each...just in case there's a bug with
        # multiple related items

        (models.TestAttribute(test=test, attribute='myattr', value='myval')
         .save())
        (models.TestAttribute(test=test, attribute='myattr2', value='myval2')
         .save())

        # can't use models to add these, since they don't have real primary keys
        self._add_iteration_keyval('iteration_attributes', test=test,
                                   iteration=1, attribute='iattr',
                                   value='ival')
        self._add_iteration_keyval('iteration_attributes', test=test,
                                   iteration=1, attribute='iattr2',
                                   value='ival2')
        self._add_iteration_keyval('iteration_result', test=test,
                                   iteration=1, attribute='iresult',
                                   value=1)
        self._add_iteration_keyval('iteration_result', test=test,
                                   iteration=1, attribute='iresult2',
                                   value=2)

        self._add_test_label(test, 'testlabel')
        self._add_test_label(test, 'testlabel2')


    def _add_iteration_keyval(self, table, test, iteration, attribute, value):
        cursor = connection.cursor()
        cursor.execute('INSERT INTO %s ' 'VALUES (%%s, %%s, %%s, %%s)' % table,
                       (test.test_idx, iteration, attribute, value))


    def _add_test_label(self, test, label_name):
        test_label = models.TestLabel(name=label_name)
        test_label.save()
        test_label.tests.add(test)


    def test_get_detailed_test_views(self):
        test = rpc_interface.get_detailed_test_views()[0]

        self.assertEquals(test['test_name'], 'mytest')
        self.assertEquals(test['job_tag'], 'myjobtag')
        self.assertEquals(test['job_name'], 'myjob')
        self.assertEquals(test['job_owner'], 'myuser')
        self.assertEquals(test['status'], 'GOOD')
        self.assertEquals(test['hostname'], 'host1')
        self.assertEquals(test['kernel'], 'mykernel')

        self.assertEquals(test['attributes'], {'myattr': 'myval',
                                               'myattr2': 'myval2'})
        self.assertEquals(test['iterations'], [{'attr': {'iattr': 'ival',
                                                         'iattr2': 'ival2'},
                                                'perf': {'iresult': 1,
                                                         'iresult2': 2}}])
        self.assertEquals(test['labels'], ['testlabel', 'testlabel2'])


    def test_test_attributes(self):
        rpc_interface.set_test_attribute('foo', 'bar', test_name='mytest')
        test = rpc_interface.get_detailed_test_views()[0]
        self.assertEquals(test['attributes'], {'foo': 'bar',
                                               'myattr': 'myval',
                                               'myattr2': 'myval2'})

        rpc_interface.set_test_attribute('foo', 'goo', test_name='mytest')
        test = rpc_interface.get_detailed_test_views()[0]
        self.assertEquals(test['attributes'], {'foo': 'goo',
                                               'myattr': 'myval',
                                               'myattr2': 'myval2'})

        rpc_interface.set_test_attribute('foo', None, test_name='mytest')
        test = rpc_interface.get_detailed_test_views()[0]
        self.assertEquals(test['attributes'], {'myattr': 'myval',
                                               'myattr2': 'myval2'})


    def test_immutable_attributes(self):
        self.assertRaises(ValueError, rpc_interface.set_test_attribute,
                          'myattr', 'foo', test_name='mytest')


if __name__ == '__main__':
    unittest.main()
