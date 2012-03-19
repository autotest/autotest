#!/usr/bin/python

__author__ = """Jiri Zupka (jzupka@redhat.com)"""

import unittest
import socket, threading, time, pickle, os
try:
    import autotest.common as common
except ImportError:
    import common
from autotest_lib.client.common_lib.test_utils import mock
from autotest_lib.client.common_lib import error, base_syncdata, barrier
syncdata = base_syncdata


class Test(unittest.TestCase):

    def setUp(self):
        self.god = mock.mock_god()
        self.god.mock_io()

    def tearDown(self):
        self.god.unmock_io()

    def test_send_receive_net_object(self):
        ls = barrier.listen_server(port=syncdata._DEFAULT_PORT)

        send_data = {'aa': ['bb', 'xx', ('ss')]}
        server = self._start_server(ls, send_data)

        recv_data = self._client("127.0.0.1", 10)
        server.join()
        ls.close()

        self.assertEqual(recv_data, send_data)

    def test_send_receive_net_object_close_connection(self):
        ls = barrier.listen_server(port=syncdata._DEFAULT_PORT)

        server = self._start_server(ls)

        with self.assertRaisesRegexp(error.NetCommunicationError,
                                     "Failed to receive python"
                                     " object over the network."):
            self._client("127.0.0.1", 2)
        server.join()
        ls.close()

    def test_send_receive_net_object_timeout(self):
        ls = barrier.listen_server(port=syncdata._DEFAULT_PORT)

        server = self._start_server(ls, timewait=5)

        with self.assertRaisesRegexp(error.NetCommunicationError,
                                     "Failed to receive python"
                                     " object over the network."):
            self._client("127.0.0.1", 2)
        server.join()
        ls.close()

    def test_send_receive_net_object_timeout_in_communication(self):
        ls = barrier.listen_server(port=syncdata._DEFAULT_PORT)

        send_data = {'aa': ['bb', 'xx', ('ss')]}
        server = self._start_server(ls, send_data,
                                    timewait=5, connbreak=True)

        with self.assertRaisesRegexp(error.NetCommunicationError,
                                     "Connection timeout."):
            self._client("127.0.0.1", 2)
        server.join()
        ls.close()

    def _start_server(self, listen_server, obj=None, timewait=None,
                      connbreak=False):
        def _server_thread(listen_server, obj=None, timewait=None,
                           connbreak=False):
            sock = listen_server.socket.accept()[0]
            if not connbreak:
                if timewait is not None:
                    time.sleep(timewait)
                if obj is not None:
                    syncdata.net_send_object(sock, obj)
            else:
                data = pickle.dumps(obj, pickle.HIGHEST_PROTOCOL)
                sock.sendall("%6d" % len(data))
                for _ in range(timewait):
                    time.sleep(1)
                    sock.sendall(".")
            sock.close()

        server_thread = threading.Thread(target=_server_thread,
                                         args=(listen_server, obj,
                                               timewait, connbreak))
        server_thread.start()
        return server_thread

    def _client(self, addr, timeout):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((addr, syncdata._DEFAULT_PORT))
        obj = syncdata.net_recv_object(sock, timeout)
        sock.close()
        return obj

    def test_SyncListenServer_start_close(self):
        sync_ls = syncdata.SyncListenServer("/tmp/")
        os.kill(sync_ls.server_pid, 0)
        time.sleep(2)
        sync_ls.close()
        l = lambda : os.kill(sync_ls.server_pid, 0)
        self.assertRaises(OSError, l)

    def test_SyncData_tmp_missing(self):
        with  self.assertRaisesRegexp(error.DataSyncError,
                                      "Tmpdir can not be None."):
            syncdata.SyncData("127.0.0.1", "127.0.0.1", ["127.0.0.1"],
                              "127.0.0.1#1")

    def test_SyncData_with_listenServer(self):
        sync_ls = syncdata.SyncListenServer("/tmp/")
        sync = syncdata.SyncData("127.0.0.1", "127.0.0.1", ["127.0.0.1"],
                                 "127.0.0.1#1", sync_ls)
        data = sync.sync("test1")
        sync.close()
        sync_ls.close()
        self.assertEqual(data, {'127.0.0.1': 'test1'})

    def test_SyncData_with_self_listen_server(self):
        sync = syncdata.SyncData("127.0.0.1", "127.0.0.1", ["127.0.0.1"],
                                 "127.0.0.1#1", tmpdir="/tmp/")
        os.kill(sync.listen_server.server_pid, 0)
        data = sync.sync("test2")
        sync.close()
        l = lambda : os.kill(sync.listen_server.server_pid, 0)
        self.assertRaises(OSError, l)
        self.assertEqual(data, {'127.0.0.1': 'test2'})

    def test_SyncData_with_listenServer_auto_close(self):
        sync = syncdata.SyncData("127.0.0.1", "127.0.0.1", ["127.0.0.1"],
                                 "127.0.0.1#1", tmpdir="/tmp/")
        os.kill(sync.listen_server.server_pid, 0)
        data = sync.one_sync("test3")
        l = lambda: os.kill(sync.listen_server.server_pid, 0)
        self.assertRaises(OSError, l)
        self.assertEqual(data, {'127.0.0.1': 'test3'})

    def test_SyncData_with_closed_listenServer(self):
        sync_ls = syncdata.SyncListenServer("/tmp/")
        sync_ls.close()
        time.sleep(2)
        sync = syncdata.SyncData("127.0.0.1", "127.0.0.1", ["127.0.0.1"],
                                 "127.0.0.1#1", sync_ls)

        l = lambda: sync.sync("test1", 2)
        self.assertRaises(error.DataSyncError, l)

    class MockListenServer(syncdata.SyncListenServer):
        def _server(self):
            self.listen_server = barrier.listen_server()
            self.exit_event.wait()

    def test_SyncData_with_listenServer_client_wait_timeout(self):
        sync = syncdata.SyncData("127.0.0.1", "127.0.0.1",
                                 ["127.0.0.1", "192.168.0.1"],
                                 "127.0.0.1#1", tmpdir="/tmp/")

        l = lambda: sync.one_sync("test1", 2)
        self.assertRaises(error.DataSyncError, l)

    def test_SyncData_with_listenServer_fake_server(self):
        sync = syncdata.SyncData("127.0.0.1", "127.0.0.1",
                                 ["127.0.0.1", "192.168.0.1"],
                                 "127.0.0.1#1", self.MockListenServer("/tmp/"))

        l = lambda: sync.one_sync("test1", 10)
        self.assertRaises(error.DataSyncError, l)

    def test_SyncData_multiple_session(self):
        data_check = {}
        threads = []
        sync_ls = syncdata.SyncListenServer("/tmp/")
        def _client_session_thread(sync_ls, data_check, id):
            sync = syncdata.SyncData("127.0.0.1", "127.0.0.1", ["127.0.0.1"],
                                 "127.0.0.1#%d" % id, sync_ls)
            data_check[id] = sync.sync("test%d" % (id))
            sync.close()

        for id in range(30):
            server_thread = threading.Thread(target=_client_session_thread,
                                             args=(sync_ls, data_check, id))
            threads.append(server_thread)
            server_thread.start()

        for th in threads:
            th.join()

        sync_ls.close()
        for id in range(30):
            self.assertEqual(data_check[id], {'127.0.0.1': 'test%d' % (id)})

if __name__ == "__main__":
    #import sys;sys.argv = ['', 'Test.testName']
    unittest.main()
