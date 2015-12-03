import errno
import logging
import pickle
import signal
import socket
import threading
import time

from autotest.client import parallel
from autotest.client.shared import autotemp
from autotest.client.shared import barrier
from autotest.client.shared import error
from autotest.client.shared import utils

_DEFAULT_PORT = 13234
_DEFAULT_TIMEOUT = 10


def net_send_object(sock, obj):
    """
    Send python object over network.

    :param ip_addr: ipaddres of waiter for data.
    :param obj: object to send
    """
    data = pickle.dumps(obj, pickle.HIGHEST_PROTOCOL)
    sock.sendall("%10d" % (len(data)))
    sock.sendall(data)


def net_recv_object(sock, timeout=60):
    """
    Receive python object over network.

    :param ip_addr: ipaddres of waiter for data.
    :param obj: object to send
    :return: object from network
    """
    try:
        endtime = time.time() + timeout
        data = ""
        d_len = int(sock.recv(10))

        while (len(data) < d_len):
            sock.settimeout(endtime - time.time())
            data += sock.recv(d_len - len(data))
        data = pickle.loads(data)
        return data
    except (socket.timeout, ValueError), e:
        raise error.NetCommunicationError("Failed to receive python"
                                          " object over the network.")


class SessionData(object):

    def __init__(self, hosts, timeout):
        self.hosts = hosts
        self.endtime = time.time() + timeout
        self.sync_data = {}
        self.connection = {}
        self.data_lock = threading.Lock()
        self.data_recv = 0
        self._finished = False

    def set_finish(self):
        self._finished = True

    def is_finished(self):
        return self._finished

    def timeout(self):
        timeout = self.endtime - time.time()
        if timeout < 0:
            timeout = 0
        return timeout

    def close(self):
        for connection in self.connection.values():
            connection[0].close()


class TempDir(autotemp.tempdir):

    """
    TempDir class is tempdir for predefined tmpdir.
    """

    def __init__(self, tmpdir=None):
        self.name = tmpdir

    def clean(self):
        """
        Should not delete predefined tmpdir.
        """
        self.name = None


class SyncListenServer(object):

    def __init__(self, address='', port=_DEFAULT_PORT, tmpdir=None):
        """
        :param address: Address on which server must be started.
        :param port: Port of server.
        :param tmpdir: Dir where pid file is saved.
        """
        if tmpdir:
            self.tmpdir = TempDir(tmpdir)
        else:
            self.tmpdir = autotemp.tempdir(unique_id='',
                                           prefix=("SyncListenServer_%d" %
                                                   port))
        self.sessions = {}
        self.exit_event = threading.Event()

        self.server_pid = parallel.fork_start(self.tmpdir.name,
                                              lambda: self._start_server(
                                                  address, port))

    def __del__(self):
        if self.tmpdir.name:
            logging.error("SyncListenServer on port %d was not closed." %
                          self.port)
            self.close()

    def _clean_sessions(self):
        """
        Close and delete timed-out connection.
        """
        to_del = []
        for session_id, session in self.sessions.items():
            if session.data_lock.acquire(False):
                if ((not session.is_finished() and not session.timeout()) or
                        session.is_finished()):
                    if not session.is_finished():
                        logging.warn("Sync session %s timed out and will"
                                     " be closed and deleted." %
                                     (session.hosts))
                    session.close()
                    to_del.append(session_id)
                session.data_lock.release()
        for td in to_del:
            del(self.sessions[td])

    def _recv_data(self, connection, session):
        session.data_lock.acquire()
        client, addr = connection
        session.connection[addr[0]] = connection

        try:
            logging.debug("Try recv from client")
            session.sync_data[addr[0]] = net_recv_object(client,
                                                         _DEFAULT_TIMEOUT)
            session.data_recv += 1
        except socket.timeout:
            logging.warn("Fail to communicate with client"
                         " %s. Synchronization of data "
                         "is not possible." % (addr))
        except error.NetCommunicationError:
            pass

        if not session.is_finished():
            if (session.data_recv == len(session.hosts) and
                    session.timeout()):
                for client, _ in session.connection.values():
                    try:
                        net_send_object(client, session.sync_data)
                        net_recv_object(client, _DEFAULT_TIMEOUT)
                    except (socket.timeout, error.NetCommunicationError):
                        self._clean_sessions()
                session.set_finish()
        session.data_lock.release()

    def __call__(self, signum, frame):
        self.exit_event.set()

    def _start_server(self, address, port):
        signal.signal(signal.SIGTERM, self)
        self.server_thread = utils.InterruptedThread(self._server,
                                                     (address, port))
        self.server_thread.start()

        while not self.exit_event.isSet():
            signal.pause()

        self.server_thread.join(2 * _DEFAULT_TIMEOUT)
        logging.debug("Server thread finished.")
        for session in self.sessions.itervalues():
            session.close()
        self.listen_server.close()
        logging.debug("ListenServer closed finished.")

    def _server(self, address, port):
        self.listen_server = barrier.listen_server(address, port)
        logging.debug("Wait for clients")
        self.listen_server.socket.settimeout(_DEFAULT_TIMEOUT)
        while not self.exit_event.isSet():
            try:
                connection = self.listen_server.socket.accept()
                logging.debug("Client %s connected.", connection[1][0])
                session_id, hosts, timeout = net_recv_object(connection[0],
                                                             _DEFAULT_TIMEOUT)
                self._clean_sessions()
                if session_id not in self.sessions:
                    logging.debug("Add new session")
                    self.sessions[session_id] = SessionData(hosts, timeout)

                logging.debug("Start recv thread.")
                utils.InterruptedThread(self._recv_data, (connection,
                                                          self.sessions[session_id])).start()

            except (socket.timeout, error.NetCommunicationError):
                self._clean_sessions()
        logging.debug("SyncListenServer on closed.")

    def close(self):
        """
        Close SyncListenServer thread.

        Close all open connection with clients and listen server.
        """
        utils.signal_pid(self.server_pid, signal.SIGTERM)
        if utils.pid_is_alive(self.server_pid):
            parallel.fork_waitfor_timed(self.tmpdir.name, self.server_pid,
                                        2 * _DEFAULT_TIMEOUT)
        self.tmpdir.clean()
        logging.debug("SyncListenServer was killed.")


class SyncData(object):

    """
    Provides data synchronization between hosts.

    Transferred data is pickled and sent to all destination points.
    If there is no listen server it will create a new one. If multiple hosts
    wants to communicate with each other, then communications are identified
    by session_id.
    """

    def __init__(self, masterid, hostid, hosts, session_id=None,
                 listen_server=None, port=13234, tmpdir=None):
        self.port = port
        self.hosts = hosts
        self.session_id = session_id
        self.endtime = None

        self.hostid = hostid
        self.masterid = masterid
        self.master = self.hostid == self.masterid
        self.connection = []
        self.server = None
        self.killserver = False

        self.listen_server = listen_server
        if not self.listen_server and self.master:
            self.listen_server = SyncListenServer(port=self.port,
                                                  tmpdir=tmpdir)
            self.killserver = True

        self.sync_data = {}

    def close(self):
        if self.killserver:
            self.listen_server.close()

    def timeout(self):
        timeout = self.endtime - time.time()
        if timeout < 0:
            timeout = 0
        return timeout

    def _client(self, data, session_id, timeout):
        if session_id is None:
            session_id = self.session_id
        session_id = str(session_id)
        self.endtime = time.time() + timeout
        logging.debug("calling master: %s", self.hosts[0])
        while self.timeout():
            try:
                self.server = socket.socket(socket.AF_INET,
                                            socket.SOCK_STREAM)
                self.server.settimeout(self.timeout())
                self.server.connect((self.masterid, self.port))

                self.server.settimeout(self.timeout())
                net_send_object(self.server, (session_id, self.hosts,
                                              self.timeout()))

                net_send_object(self.server, data)
                self.sync_data = net_recv_object(self.server,
                                                 self.timeout())
                net_send_object(self.server, "BYE")
                break
            except error.NetCommunicationError:
                logging.warn("Problem with communication with server.")
                self.server.close()
                self.server = None
                time.sleep(1)
            except socket.timeout:
                logging.warn("timeout calling host %s, retry" %
                             (self.masterid))
                time.sleep(1)
            except socket.error, err:
                (code, _) = err
                if (code != errno.ECONNREFUSED):
                    raise
                time.sleep(1)
        if not self.timeout():
            raise error.DataSyncError("Timeout during data sync with data %s" %
                                      (data))

    def sync(self, data=None, timeout=60, session_id=None):
        """
        Synchronize data between hosts.
        """
        try:
            self._client(data, session_id, timeout)
        finally:
            if self.server:
                self.server.close()
        return self.sync_data

    def single_sync(self, data=None, timeout=60, session_id=None):
        try:
            self.sync(data, timeout, session_id)
        finally:
            self.close()
        return self.sync_data
