import socket
import errno
import logging
from time import time, sleep
from autotest.client.shared import error

# default barrier port
_DEFAULT_PORT = 11922


def get_host_from_id(hostid):
    # Remove any trailing local identifier following a #.
    # This allows multiple members per host which is particularly
    # helpful in testing.
    if not hostid.startswith('#'):
        return hostid.split('#')[0]
    else:
        raise error.BarrierError(
            "Invalid Host id: Host Address should be specified")


class BarrierAbortError(error.BarrierError):

    """Special BarrierError raised when an explicit abort is requested."""


class listen_server(object):

    """
    Manages a listening socket for barrier.

    Can be used to run multiple barrier instances with the same listening
    socket (if they were going to listen on the same port).

    Attributes:

    :attr address: Address to bind to (string).
    :attr port: Port to bind to.
    :attr socket: Listening socket object.
    """

    def __init__(self, address='', port=_DEFAULT_PORT):
        """
        Create a listen_server instance for the given address/port.

        :param address: The address to listen on.
        :param port: The port to listen on.
        """
        self.address = address
        self.port = port
        self.socket = self._setup()

    def _setup(self):
        """Create, bind and listen on the listening socket."""
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((self.address, self.port))
        sock.listen(100)

        return sock

    def close(self):
        """Close the listening socket."""
        self.socket.close()


class barrier(object):

    """Multi-machine barrier support.

    Provides multi-machine barrier mechanism.
    Execution stops until all members arrive at the barrier.

    Implementation Details:
    .......................

    When a barrier is forming the master node (first in sort order) in the
    set accepts connections from each member of the set.  As they arrive
    they indicate the barrier they are joining and their identifier (their
    hostname or IP address and optional tag).  They are then asked to wait.
    When all members are present the master node then checks that each
    member is still responding via a ping/pong exchange.  If this is
    successful then everyone has checked in at the barrier.  We then tell
    everyone they may continue via a rlse message.

    Where the master is not the first to reach the barrier the client
    connects will fail.  Client will retry until they either succeed in
    connecting to master or the overall timeout is exceeded.

    As an example here is the exchange for a three node barrier called
    'TAG'

      MASTER                        CLIENT1         CLIENT2
        <-------------TAG C1-------------
        --------------wait-------------->
                      [...]
        <-------------TAG C2-----------------------------
        --------------wait------------------------------>
                      [...]
        --------------ping-------------->
        <-------------pong---------------
        --------------ping------------------------------>
        <-------------pong-------------------------------
                ----- BARRIER conditions MET -----
        --------------rlse-------------->
        --------------rlse------------------------------>

    Note that once the last client has responded to pong the barrier is
    implicitly deemed satisifed, they have all acknowledged their presence.
    If we fail to send any of the rlse messages the barrier is still a
    success, the failed host has effectively broken 'right at the beginning'
    of the post barrier execution window.

    In addition, there is another rendezvous, that makes each slave a server
    and the master a client.  The connection process and usage is still the
    same but allows barriers from machines that only have a one-way
    connection initiation.  This is called rendezvous_servers.

    For example:
        if ME == SERVER:
            server start

        b = job.barrier(ME, 'server-up', 120)
        b.rendezvous(CLIENT, SERVER)

        if ME == CLIENT:
            client run

        b = job.barrier(ME, 'test-complete', 3600)
        b.rendezvous(CLIENT, SERVER)

        if ME == SERVER:
            server stop

    Any client can also request an abort of the job by setting
    abort=True in the rendezvous arguments.
    """

    def __init__(self, hostid, tag, timeout=None, port=None,
                 listen_server=None):
        """
        :param hostid: My hostname/IP address + optional tag.
        :param tag: Symbolic name of the barrier in progress.
        :param timeout: Maximum seconds to wait for a the barrier to meet.
        :param port: Port number to listen on.
        :param listen_server: External listen_server instance to use instead
                of creating our own.  Create a listen_server instance and
                reuse it across multiple barrier instances so that the
                barrier code doesn't try to quickly re-bind on the same port
                (packets still in transit for the previous barrier they may
                reset new connections).
        """
        self._hostid = hostid
        self._tag = tag
        if listen_server:
            if port:
                raise error.BarrierError(
                    '"port" and "listen_server" are mutually exclusive.')
            self._port = listen_server.port
        else:
            self._port = port or _DEFAULT_PORT
        self._server = listen_server  # A listen_server instance or None.
        self._members = []  # List of hosts we expect to find at the barrier.
        self._timeout_secs = timeout
        self._start_time = None  # Timestamp of when we started waiting.
        self._masterid = None  # Host/IP + optional tag of selected master.
        logging.info("tag=%s port=%d timeout=%r",
                     self._tag, self._port, self._timeout_secs)

        # Number of clients seen (should be the length of self._waiting).
        self._seen = 0

        # Clients who have checked in and are waiting (if we are a master).
        self._waiting = {}  # Maps from hostname -> (client, addr) tuples.

    def _update_timeout(self, timeout):
        if timeout is not None and self._start_time is not None:
            self._timeout_secs = (time() - self._start_time) + timeout
        else:
            self._timeout_secs = timeout

    def _remaining(self):
        if self._timeout_secs is not None and self._start_time is not None:
            timeout = self._timeout_secs - (time() - self._start_time)
            if timeout <= 0:
                errmsg = "timeout waiting for barrier: %s" % self._tag
                raise error.BarrierError(errmsg)
        else:
            timeout = self._timeout_secs

        if self._timeout_secs is not None:
            logging.info("seconds remaining: %d", timeout)
        return timeout

    def _master_welcome(self, connection):
        client, addr = connection
        name = None

        client.settimeout(5)
        try:
            # Get the clients name.
            intro = client.recv(1024)
            intro = intro.strip("\r\n")

            intro_parts = intro.split(' ', 2)
            if len(intro_parts) != 2:
                logging.warn("Ignoring invalid data from %s: %r",
                             client.getpeername(), intro)
                client.close()
                return
            tag, name = intro_parts

            logging.info("new client tag=%s, name=%s", tag, name)

            # Ok, we know who is trying to attach.  Confirm that
            # they are coming to the same meeting.  Also, everyone
            # should be using a unique handle (their IP address).
            # If we see a duplicate, something _bad_ has happened
            # so drop them now.
            if self._tag != tag:
                logging.warn("client arriving for the wrong barrier: %s != %s",
                             self._tag, tag)
                client.settimeout(5)
                client.send("!tag")
                client.close()
                return
            elif name in self._waiting:
                logging.warn("duplicate client")
                client.settimeout(5)
                client.send("!dup")
                client.close()
                return

            # Acknowledge the client
            client.send("wait")

        except socket.timeout:
            # This is nominally an error, but as we do not know
            # who that was we cannot do anything sane other
            # than report it and let the normal timeout kill
            # us when thats appropriate.
            logging.warn("client handshake timeout: (%s:%d)",
                         addr[0], addr[1])
            client.close()
            return

        logging.info("client now waiting: %s (%s:%d)",
                     name, addr[0], addr[1])

        # They seem to be valid record them.
        self._waiting[name] = connection
        self._seen += 1

    def _slave_hello(self, connection):
        (client, addr) = connection
        name = None

        client.settimeout(5)
        try:
            client.send(self._tag + " " + self._hostid)

            reply = client.recv(4)
            reply = reply.strip("\r\n")
            logging.info("master said: %s", reply)

            # Confirm the master accepted the connection.
            if reply != "wait":
                logging.warn("Bad connection request to master")
                client.close()
                return

        except socket.timeout:
            # This is nominally an error, but as we do not know
            # who that was we cannot do anything sane other
            # than report it and let the normal timeout kill
            # us when thats appropriate.
            logging.error("master handshake timeout: (%s:%d)",
                          addr[0], addr[1])
            client.close()
            return

        logging.info("slave now waiting: (%s:%d)", addr[0], addr[1])

        # They seem to be valid record them.
        self._waiting[self._hostid] = connection
        self._seen = 1

    def _master_release(self):
        # Check everyone is still there, that they have not
        # crashed or disconnected in the meantime.
        allpresent = True
        abort = self._abort
        for name in self._waiting:
            (client, addr) = self._waiting[name]

            logging.info("checking client present: %s", name)

            client.settimeout(5)
            reply = 'none'
            try:
                client.send("ping")
                reply = client.recv(1024)
            except socket.timeout:
                logging.warn("ping/pong timeout: %s", name)
                pass

            if reply == 'abrt':
                logging.warn("Client %s requested abort", name)
                abort = True
            elif reply != "pong":
                allpresent = False

        if not allpresent:
            raise error.BarrierError("master lost client")

        if abort:
            logging.info("Aborting the clients")
            msg = 'abrt'
        else:
            logging.info("Releasing clients")
            msg = 'rlse'

        # If every ones checks in then commit the release.
        for name in self._waiting:
            (client, addr) = self._waiting[name]

            client.settimeout(5)
            try:
                client.send(msg)
            except socket.timeout:
                logging.warn("release timeout: %s", name)
                pass

        if abort:
            raise BarrierAbortError("Client requested abort")

    def _waiting_close(self):
        # Either way, close out all the clients.  If we have
        # not released them then they know to abort.
        for name in self._waiting:
            (client, addr) = self._waiting[name]

            logging.info("closing client: %s", name)

            try:
                client.close()
            except Exception:
                pass

    def _run_server(self, is_master):
        server = self._server or listen_server(port=self._port)
        failed = 0
        try:
            while True:
                try:
                    # Wait for callers welcoming each.
                    server.socket.settimeout(self._remaining())
                    connection = server.socket.accept()
                    if is_master:
                        self._master_welcome(connection)
                    else:
                        self._slave_hello(connection)
                except socket.timeout:
                    logging.warn("timeout waiting for remaining clients")
                    pass

                if is_master:
                    # Check if everyone is here.
                    logging.info("master seen %d of %d",
                                 self._seen, len(self._members))
                    if self._seen == len(self._members):
                        self._master_release()
                        break
                else:
                    # Check if master connected.
                    if self._seen:
                        logging.info("slave connected to master")
                        self._slave_wait()
                        break
        finally:
            self._waiting_close()
            # if we created the listening_server in the beginning of this
            # function then close the listening socket here
            if not self._server:
                server.close()

    def _run_client(self, is_master):
        while self._remaining() is None or self._remaining() > 0:
            try:
                remote = socket.socket(socket.AF_INET,
                                       socket.SOCK_STREAM)
                remote.settimeout(30)
                if is_master:
                    # Connect to all slaves.
                    host = get_host_from_id(self._members[self._seen])
                    logging.info("calling slave: %s", host)
                    connection = (remote, (host, self._port))
                    remote.connect(connection[1])
                    self._master_welcome(connection)
                else:
                    # Just connect to the master.
                    host = get_host_from_id(self._masterid)
                    logging.info("calling master")
                    connection = (remote, (host, self._port))
                    remote.connect(connection[1])
                    self._slave_hello(connection)
            except socket.timeout:
                logging.warn("timeout calling host, retry")
                sleep(10)
                pass
            except socket.error, err:
                (code, str) = err
                if (code != errno.ECONNREFUSED):
                    raise
                sleep(10)

            if is_master:
                # Check if everyone is here.
                logging.info("master seen %d of %d",
                             self._seen, len(self._members))
                if self._seen == len(self._members):
                    self._master_release()
                    break
            else:
                # Check if master connected.
                if self._seen:
                    logging.info("slave connected to master")
                    self._slave_wait()
                    break

        self._waiting_close()

    def _slave_wait(self):
        remote = self._waiting[self._hostid][0]
        mode = "wait"
        while True:
            # All control messages are the same size to allow
            # us to split individual messages easily.
            remote.settimeout(self._remaining())
            reply = remote.recv(4)
            if not reply:
                break

            reply = reply.strip("\r\n")
            logging.info("master said: %s", reply)

            mode = reply
            if reply == "ping":
                # Ensure we have sufficient time for the
                # ping/pong/rlse cyle to complete normally.
                self._update_timeout(10 + 10 * len(self._members))

                if self._abort:
                    msg = "abrt"
                else:
                    msg = "pong"
                logging.info(msg)
                remote.settimeout(self._remaining())
                remote.send(msg)

            elif reply == "rlse" or reply == "abrt":
                # Ensure we have sufficient time for the
                # ping/pong/rlse cyle to complete normally.
                self._update_timeout(10 + 10 * len(self._members))

                logging.info("was released, waiting for close")

        if mode == "rlse":
            pass
        elif mode == "wait":
            raise error.BarrierError("master abort -- barrier timeout")
        elif mode == "ping":
            raise error.BarrierError("master abort -- client lost")
        elif mode == "!tag":
            raise error.BarrierError("master abort -- incorrect tag")
        elif mode == "!dup":
            raise error.BarrierError("master abort -- duplicate client")
        elif mode == "abrt":
            raise BarrierAbortError("Client requested abort")
        else:
            raise error.BarrierError("master handshake failure: " + mode)

    def rendezvous(self, *hosts, **dargs):
        # if called with abort=True, this will raise an exception
        # on all the clients.
        self._start_time = time()
        self._members = list(hosts)
        self._members.sort()
        self._masterid = self._members.pop(0)
        self._abort = dargs.get('abort', False)

        logging.info("masterid: %s", self._masterid)
        if self._abort:
            logging.debug("%s is aborting", self._hostid)
        if not len(self._members):
            logging.info("No other members listed.")
            return
        logging.info("members: %s", ",".join(self._members))

        self._seen = 0
        self._waiting = {}

        # Figure out who is the master in this barrier.
        if self._hostid == self._masterid:
            logging.info("selected as master")
            self._run_server(is_master=True)
        else:
            logging.info("selected as slave")
            self._run_client(is_master=False)

    def rendezvous_servers(self, masterid, *hosts, **dargs):
        # if called with abort=True, this will raise an exception
        # on all the clients.
        self._start_time = time()
        self._members = list(hosts)
        self._members.sort()
        self._masterid = masterid
        self._abort = dargs.get('abort', False)

        logging.info("masterid: %s", self._masterid)
        if not len(self._members):
            logging.info("No other members listed.")
            return
        logging.info("members: %s", ",".join(self._members))

        self._seen = 0
        self._waiting = {}

        # Figure out who is the master in this barrier.
        if self._hostid == self._masterid:
            logging.info("selected as master")
            self._run_client(is_master=True)
        else:
            logging.info("selected as slave")
            self._run_server(is_master=False)
