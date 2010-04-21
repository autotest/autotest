#!/usr/bin/python

import common
import unittest
from autotest_lib.frontend import setup_django_environment
from autotest_lib.frontend import setup_test_environment
from autotest_lib.client.common_lib.test_utils import mock
from autotest_lib.frontend.shared import resource_test_utils
from autotest_lib.frontend.tko import models, rpc_interface_unittest


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
