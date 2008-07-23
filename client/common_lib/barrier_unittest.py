#!/usr/bin/python2.4

__author__ = """Ashwin Ganti (aganti@google.com)"""

import os, sys, socket, errno, unittest, threading
from time import time, sleep
import common
from autotest_lib.client.common_lib import error, barrier
from autotest_lib.client.common_lib.test_utils import mock

class barrier_test(unittest.TestCase):

    def setUp(self):
        self.god = mock.mock_god()
        self.god.mock_io()


    def tearDown(self):
        self.god.unmock_io()


    def test_initialize(self):
        b = barrier.barrier('127.0.0.1#', 'testtag', 100, 63001)
        self.assertEqual(b.hostid, '127.0.0.1#')
        self.assertEqual(b.tag, 'testtag')
        self.assertEqual(b.timeout, 100)
        self.assertEqual(b.port, 63001)


    def test_get_host_from_id(self):
        b = barrier.barrier('127.0.0.1#', 'testgethost', 100)

        hostname = b.get_host_from_id('my_host')
        self.assertEqual(hostname, 'my_host')

        hostname = b.get_host_from_id('my_host#')
        self.assertEqual(hostname, 'my_host')

        self.assertRaises(error.BarrierError, b.get_host_from_id, '#my_host')


    def test_update_timeout(self):
        b = barrier.barrier('127.0.0.1#', 'update', 100)
        b.update_timeout(120)
        self.assertEqual(b.timeout, 120)


    def test_remaining(self):
        b = barrier.barrier('127.0.0.1#', 'remain', 100)
        remain = b.remaining()
        self.assertEqual(remain, 100)


    def test_rendevous_basic(self):
        # Basic rendevous testing
        self.rendevous_test(60, port=63100)


    def test_rendevous_timeout(self):
        # The rendevous should time out here and throw a
        # BarrierError since we are specifying a timeout of 0
        self.assertRaises(error.BarrierError,
                          self.rendevous_test, 0, port=63101)


    def test_rendevous_servers_basic(self):
        # The rendevous should time out here and throw a
        # BarrierError since we are specifying a timeout of 0
        self.rendevous_test(60, port=63001,
                            rendevous_servers=True)


    def test_rendevous_servers_timeout(self):
        # The rendevous should time out here and throw a
        # BarrierError since we are specifying a timeout of 0
        self.assertRaises(error.BarrierError,
                          self.rendevous_test, 0, port=63002,
                          rendevous_servers=True)


    # Internal utility function (not a unit test)
    def rendevous_test(self, timeout, port=63000, rendevous_servers=False):
        def _rdv(addr):
            b1 = barrier.barrier(addr, "test_meeting", timeout, port)
            if not rendevous_servers:
                b1.rendevous('127.0.0.1#0', '127.0.0.1#1')
            else:
                b1.rendevous_servers('127.0.0.1#0', '127.0.0.1#1')

        def _thread_rdv(addr):
            # We need to ignore the exception on one side.
            try:
                _rdv(addr)
            except error.BarrierError:
                if timeout == 0:
                    pass

        client = threading.Thread(target=_thread_rdv,
                                  args=('127.0.0.1#0',))
        client.start()
        _rdv('127.0.0.1#1')
        client.join()


if __name__ == "__main__":
    unittest.main()
