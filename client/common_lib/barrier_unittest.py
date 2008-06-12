#!/usr/bin/python2.4

__author__ = """Ashwin Ganti (aganti@google.com)"""

import os, sys, socket, errno, unittest
from time import time, sleep
import error, barrier
from test_utils import mock

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

        try:
            hostname = b.get_host_from_id('#my_host')
        except barrier.BarrierError, e:
            pass
        else:
            self.fail('Expecting a BarrierError for invalid host id,'
                      'but did not get one')


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
        try:
            self.rendevous_test(60, port=63100)
        except barrier.BarrierError, e:
            self.fail("Encountered a barrier error")


    def test_rendevous_timeout(self):
        # The rendevous should time out here and throw a
        # BarrierError since we are specifying a timeout of 0
        try:
            self.rendevous_test(0, port=63101)
        except barrier.BarrierError, e:
            pass
        else:
            self.fail('Expecting a BarrierError,'
                      'but did not get one')


    def test_rendevous_servers_basic(self):
        # The rendevous should time out here and throw a
        # BarrierError since we are specifying a timeout of 0
        try:
            self.rendevous_test(60, port=63001,
                                rendevous_servers=True)
        except barrier.BarrierError, e:
            self.fail("Encountered a barrier error")


    def test_rendevous_servers_timeout(self):
        # The rendevous should time out here and throw a
        # BarrierError since we are specifying a timeout of 0
        try:
            self.rendevous_test(0, port=63002,
                                rendevous_servers=True)
        except barrier.BarrierError, e:
            pass
        else:
            self.fail('Expecting a BarrierError,'
                      'but did not get one')


    # Internal utility function (not a unit test)
    def rendevous_test(self, timeout, port=63000, rendevous_servers=False):
        try:
            pid = os.fork()
            if pid:
                b = barrier.barrier('127.0.0.1#1',
                            "test_meeting", timeout, port)
                if not rendevous_servers:
                    b.rendevous('127.0.0.1#0',
                                '127.0.0.1#1')
                else:
                    b.rendevous_servers('127.0.0.1#0',
                                        '127.0.0.1#1')
                os.wait()
            else:
                b1 = barrier.barrier('127.0.0.1#0',
                            "test_meeting", timeout, port)
                if not rendevous_servers:
                    b1.rendevous('127.0.0.1#0',
                                 '127.0.0.1#1')
                else:
                    b1.rendevous_servers('127.0.0.1#0',
                                         '127.0.0.1#1')

        except OSError, e:
            self.fail("fork failed")


if __name__ == "__main__":
    unittest.main()
