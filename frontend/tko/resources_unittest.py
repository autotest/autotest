#!/usr/bin/python

try:
    import autotest.common as common  # pylint: disable=W0611
except ImportError:
    import common  # pylint: disable=W0611
import unittest

from autotest.frontend import setup_django_environment  # pylint: disable=W0611
from autotest.frontend import setup_test_environment  # pylint: disable=W0611
from autotest.client.shared.test_utils import mock
from autotest.frontend.shared import resource_test_utils
from autotest.frontend.tko import rpc_interface_unittest


class TkoResourceTestCase(resource_test_utils.ResourceTestCase,
                          rpc_interface_unittest.TkoTestMixin):
    URI_PREFIX = 'http://testserver/new_tko/server/resources'

    def setUp(self):
        super(TkoResourceTestCase, self).setUp()
        self.god = mock.mock_god()
        self._patch_sqlite_stuff()
        self._create_initial_data()

    def tearDown(self):
        super(TkoResourceTestCase, self).tearDown()
        self.god.unstub_all()


class TestResultTest(TkoResourceTestCase):

    def test_collection(self):
        response = self.request('get', 'test_results')
        self.check_collection(response, 'test_name',
                              ['kernbench', 'mytest1', 'mytest2'])

    def test_filter_afe_job_id(self):
        response = self.request('get', 'test_results?afe_job_id=1')
        self.check_collection(response, 'test_name', ['mytest1', 'mytest2'])

    def test_entry(self):
        response = self.request('get', 'test_results/1')
        self.assertEquals(response['test_name'], 'mytest1')
        self.assertEquals(response['status'], 'GOOD')
        self.assertEquals(response['reason'], '')


if __name__ == '__main__':
    unittest.main()
