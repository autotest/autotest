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

def setup_test_view():
    """
    Django has no way to actually represent a view; we simply create a model for
    TestView.   This means when we syncdb, Django will create a table for it.
    So manually remove that table and replace it with a view.
    """
    cursor = connection.cursor()
    cursor.execute('DROP TABLE test_view_2')
    cursor.execute(_CREATE_TEST_VIEW)


class RpcInterfaceTest(unittest.TestCase):
    def setUp(self):
        setup_test_environment.set_up()
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

        attribute = models.TestAttribute(test=test, attribute='myattr',
                                         value='myval')
        attribute.save()

        iteration_attribute = models.IterationAttribute(test=test, iteration=1,
                                                        attribute='iattr',
                                                        value='ival')
        iteration_result = models.IterationResult(test=test, iteration=1,
                                                  attribute='iresult',
                                                  value=1)
        iteration_attribute.save()
        iteration_result.save()

        test_label = models.TestLabel(name='testlabel')
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

        self.assertEquals(test['attributes'], {'myattr' : 'myval'})
        self.assertEquals(test['iterations'], [{'attr' : {'iattr' : 'ival'},
                                                'perf' : {'iresult' : 1}}])
        self.assertEquals(test['labels'], ['testlabel'])


    def test_test_attributes(self):
        rpc_interface.set_test_attribute('foo', 'bar', test_name='mytest')
        test = rpc_interface.get_detailed_test_views()[0]
        self.assertEquals(test['attributes'], {'foo' : 'bar',
                                               'myattr' : 'myval'})

        rpc_interface.set_test_attribute('foo', 'goo', test_name='mytest')
        test = rpc_interface.get_detailed_test_views()[0]
        self.assertEquals(test['attributes'], {'foo' : 'goo',
                                               'myattr' : 'myval'})

        rpc_interface.set_test_attribute('foo', None, test_name='mytest')
        test = rpc_interface.get_detailed_test_views()[0]
        self.assertEquals(test['attributes'], {'myattr' : 'myval'})


    def test_immutable_attributes(self):
        self.assertRaises(ValueError, rpc_interface.set_test_attribute,
                          'myattr', 'foo', test_name='mytest')


if __name__ == '__main__':
    unittest.main()
