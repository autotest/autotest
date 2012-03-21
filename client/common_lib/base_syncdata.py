import pickle, time, socket, errno, threading, logging, signal
from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib import barrier
from autotest_lib.client.common_lib import utils
from autotest_lib.client.bin import parallel

_DEFAULT_PORT = 13234
_DEFAULT_TIMEOUT = 10


def net_send_object(sock, obj):
    """
    Send python object over network.

    @param ip_addr: ipaddres of waiter for data.
    @param obj: object to send
    """
    data = pickle.dumps(obj, pickle.HIGHEST_PROTOCOL)
    sock.sendall("%6d" % (len(data)))
    sock.sendall(data)


def net_recv_object(sock, timeout=60):
    """
    Receive python object over network.

    @param ip_addr: ipaddres of waiter for data.
    @param obj: object to send
    @return: object from network
    """
    try:
        endtime = time.time() + timeout
        data = ""
        d_len = int(sock.recv(6))

        while (len(data) < d_len and (time.time() <= endtime)):
            data += sock.recv(d_len - len(data))
        if (time.time() > endtime):
            raise error.NetCommunicationError("Connection timeout.")
        data = pickle.loads(data)
        return data
    except (socket.timeout, ValueError), e:
        raise error.NetCommunicationError("Failed to receive python"
                                          " object over the network.")


class SyncListenServer(object):
    class SessionData(object):
        def __init__(self, hosts, timeout):
            self.hosts = hosts
            self.endtime = time.time() + timeout
            self.sync_data = {}
            self.connection = {}
            self.data_lock = threading.Lock()
            self.data_recv = 0
            self.finished = False

        def remaining(self):
            remaining = self.endtime - time.time()
            if remaining < 0:
                remaining = 0
            return remaining

        def close(self):
            for connection in self.connection.values():
                connection[0].close()

    """
    def __new__(cls, address='', port=_DEFAULT_PORT):
        sync_server = env.get_syncserver(port)
        self = None
        if not sync_server:
            self = super(SyncListenServer, cls).__new__(cls, address, port)
            env.register_syncserver(port, self)
        return self
    """

    def __init__(self, tmpdir, address='', port=_DEFAULT_PORT):
        """
        @param address: Address on which server must be started.
        @param port: Port of server.
        @param tmpdir: Dir where pid file is saved.
        """
        l = lambda: self._start_server(address, port)

        self.tmpdir = tmpdir
        self.sessions = {}
        self.exit_event = threading.Event()

        self.server_pid = parallel.fork_start(self.tmpdir, l)

    def _clean_sessions(self):
        """
        Delete and close connection which is timeout.
        """
        to_del = []
        for session_id, session in self.sessions.items():
            if session.data_lock.acquire(False):
                if ((not session.finished and not session.remaining()) or
                    session.finished):
                    if not session.finished:
                        logging.warn("Sync Session %s timeout." %
                                     (session.hosts))
                    session.close()
                    to_del.append(session_id)
                session.data_lock.release()
        for td in to_del:
            del(self.sessions[td])

    def _recv_data(self, connection, session):
        with session.data_lock:
            client, addr = connection
            session.connection[addr[0]] = connection

            try:
                logging.info("Try recv from client")
                session.sync_data[addr[0]] = net_recv_object(client,
                                                             _DEFAULT_TIMEOUT)
                logging.info("Try recv from client")
                session.data_recv += 1
            except socket.timeout:
                raise error.DataSyncError("Fail to communicate with client"
                                          " %s. Synchronization of data "
                                          "is not possible" % (addr))
            except error.NetCommunicationError:
                pass

        with session.data_lock:
            if not session.finished:
                if (session.data_recv == len(session.hosts) and
                    session.remaining()):
                    for client, _ in session.connection.values():
                        net_send_object(client, session.sync_data)
                        net_recv_object(client, _DEFAULT_TIMEOUT)
                    session.finished = True

    def __call__(self, signum, frame):
        self.exit_event.set()

    def _start_server(self, address, port):
        signal.signal(signal.SIGTERM, self)
        self.server_thread = utils.InterruptedThread(self._server,
                                                (address, port))
        self.server_thread.start()

        while not self.exit_event.is_set():
            signal.pause()

        self.server_thread.join(2 * _DEFAULT_TIMEOUT)
        for session in self.sessions.itervalues():
            session.close()
        self.listen_server.close()

    def _server(self, address, port):
        self.listen_server = barrier.listen_server(address, port)
        logging.debug("Wait for clients")
        self.listen_server.socket.settimeout(_DEFAULT_TIMEOUT)
        while not self.exit_event.is_set():
            try:
                connection = self.listen_server.socket.accept()
                logging.debug("Client %s connected.", connection[1][0])
                session_id, hosts, timeout = net_recv_object(connection[0],
                                                             _DEFAULT_TIMEOUT)
                self._clean_sessions()
                if not session_id in self.sessions:
                    logging.debug("Add new session")
                    self.sessions[session_id] = self.SessionData(hosts,
                                                                 timeout)

                utils.InterruptedThread(self._recv_data, (connection,
                                        self.sessions[session_id])).start()

            except (socket.timeout, error.NetCommunicationError):
                self._clean_sessions()

    def close(self):
        """
        Close SyncListenServer thread. Close listen server. And close all
        unclosed connection with clients.
        """
        utils.signal_pid(self.server_pid, signal.SIGTERM)
        if utils.pid_is_alive(self.server_pid):
            parallel.fork_waitfor_timed(self.tmpdir, self.server_pid,
                                        2 * _DEFAULT_TIMEOUT)

        logging.debug("SyncListenServer was killed.")


class SyncData(object):
    """
    Provides data synchronization between hosts. Transferred data
    are pickled and sent to all destination.
       If there is no listen server it create new one. If multiple host
    want communicate with each other then communication are identified
    by link_id.

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
            if tmpdir is None:
                raise error.DataSyncError("Tmpdir can not be None.")
            self.listen_server = SyncListenServer(tmpdir, port=self.port)
            self.killserver = True

        self.sync_data = {}

    def close(self):
        if self.killserver:
            self.listen_server.close()

    def _remaining(self):
        remaining = self.endtime - time.time()
        if remaining < 0:
            remaining = 0
        return remaining

    def _client(self, data, session_id, timeout):
        if session_id is None:
            session_id = self.session_id
        session_id = str(session_id)
        self.endtime = time.time() + timeout
        logging.info("calling master: %s", self.hosts[0])
        while self._remaining():
            try:
                self.server = socket.socket(socket.AF_INET,
                                            socket.SOCK_STREAM)
                self.server.settimeout(5)
                self.server.connect((self.masterid, self.port))
                self.server.settimeout(self._remaining())
                net_send_object(self.server, (session_id, self.hosts,
                                              self._remaining()))

                net_send_object(self.server, data)
                self.sync_data = net_recv_object(self.server,
                                                 self._remaining())
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
        if not self._remaining():
            raise error.DataSyncError("Timeout during data sync with data %s" %
                                      (data))

    def sync(self, data=None, timeout=60, session_id=None):
        try:
            self._client(data, session_id, timeout)
        finally:
            if self.server:
                self.server.close()
        return self.sync_data

    def one_sync(self, data=None, timeout=60, session_id=None):
        try:
            self.sync(data, timeout, session_id)
        finally:
            self.close()
        return self.sync_data
