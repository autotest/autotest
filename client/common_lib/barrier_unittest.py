#!/usr/bin/python

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
        b = barrier.barrier('127.0.0.1#', 'testtag', 100, 11921)
        self.assertEqual(b.hostid, '127.0.0.1#')
        self.assertEqual(b.tag, 'testtag')
        self.assertEqual(b.timeout, 100)
        self.assertEqual(b.port, 11921)


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


    def test_master_welcome_garbage(self):
        b = barrier.barrier('127.0.0.1#', 'garbage', 100)
        waiting_before = dict(b.waiting)
        seen_before = b.seen

        sender, receiver = socket.socketpair()
        try:
            sender.send('GET /foobar?p=-1 HTTP/1.0\r\n\r\n')
            # This should not raise an exception.
            b.master_welcome((receiver, 'fakeaddr'))

            self.assertEqual(waiting_before, b.waiting)
            self.assertEqual(seen_before, b.seen)

            sender, receiver = socket.socketpair()
            sender.send('abcdefg\x00\x01\x02\n'*5)
            # This should not raise an exception.
            b.master_welcome((receiver, 'fakeaddr'))

            self.assertEqual(waiting_before, b.waiting)
            self.assertEqual(seen_before, b.seen)
        finally:
            sender.close()
            receiver.close()


    def test_rendezvous_basic(self):
        # Basic rendezvous testing
        self.rendezvous_test(60, port=11920)


    def test_rendezvous_timeout(self):
        # The rendezvous should time out here and throw a
        # BarrierError since we are specifying a timeout of 0
        self.assertRaises(error.BarrierError,
                          self.rendezvous_test, 0, port=11921)


    def test_rendezvous_abort_ok(self):
        # Test with abort flag set to not abort.
        self.rendezvous_test(60, port=11920,
                             test_abort=True, abort=False)


    def test_rendezvous_abort(self):
        # The rendezvous should abort here and throw a
        # BarrierError since we are asking to abort
        self.assertRaises(error.BarrierError,
                          self.rendezvous_test, 0, port=11921,
                          test_abort=True, abort=True)


    def test_rendezvous_servers_basic(self):
        # The rendezvous should time out here and throw a
        # BarrierError since we are specifying a timeout of 0
        self.rendezvous_test(60, port=11921,
                             rendezvous_servers=True)


    def test_rendezvous_servers_timeout(self):
        # The rendezvous should time out here and throw a
        # BarrierError since we are specifying a timeout of 0
        self.assertRaises(error.BarrierError,
                          self.rendezvous_test, 0, port=11922,
                          rendezvous_servers=True)


    def test_rendezvous_servers_abort_ok(self):
        # Test with abort flag set to not abort.
        self.rendezvous_test(60, port=11920, rendezvous_servers=True,
                             test_abort=True, abort=False)


    def test_rendezvous_servers_abort(self):
        # The rendezvous should abort here and throw a
        # BarrierError since we are asking to abort
        self.assertRaises(error.BarrierError,
                          self.rendezvous_test, 0, port=11922,
                          rendezvous_servers=True,
                          test_abort=True, abort=True)


    # Internal utility function (not a unit test)
    def rendezvous_test(self, timeout, port=11922,
                        rendezvous_servers=False, test_abort=False,
                        abort=False):
        def _rdv(addr):
            b1 = barrier.barrier(addr, "test_meeting", timeout, port)
            if not rendezvous_servers:
                if test_abort:
                    b1.rendezvous('127.0.0.1#0', '127.0.0.1#1', abort=abort)
                else:
                    b1.rendezvous('127.0.0.1#0', '127.0.0.1#1')
            else:
                if test_abort:
                    b1.rendezvous_servers('127.0.0.1#0', '127.0.0.1#1',
                                          abort=abort)
                else:
                    b1.rendezvous_servers('127.0.0.1#0', '127.0.0.1#1')


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
