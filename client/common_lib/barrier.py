import sys, socket, errno, logging
from time import time, sleep
from autotest_lib.client.common_lib import error


class barrier(object):
    """ Multi-machine barrier support

    Provides multi-machine barrier mechanism.  Execution
    stopping until all members arrive at the barrier.

    When a barrier is forming the master node (first in sort
    order) in the set accepts connections from each member
    of the set.     As they arrive they indicate the barrier
    they are joining and their identifier (their hostname
    or IP address and optional tag).  They are then asked
    to wait.  When all members are present the master node
    then checks that each member is still responding via a
    ping/pong exchange.     If this is successful then everyone
    has checked in at the barrier.  We then tell everyone
    they may continue via a rlse message.

    Where the master is not the first to reach the barrier
    the client connects will fail.  Client will retry until
    they either succeed in connecting to master or the overal
    timeout is exceeded.

    As an example here is the exchange for a three node
    barrier called 'TAG'

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

    Note that once the last client has responded to pong the
    barrier is implicitly deemed satisifed, they have all
    acknowledged their presence.  If we fail to send any
    of the rlse messages the barrier is still a success,
    the failed host has effectively broken 'right at the
    beginning' of the post barrier execution window.

    In addition, there is another rendezvous, that makes each slave a server
    and the master a client. The connection process and usage is still the
    same but allows barriers from machines that only have a one-way
    connection initiation. This is called rendezvous_servers.

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


    Properties:
            hostid
                    My hostname/IP address + optional tag
            tag
                    Symbolic name of the barrier in progress
            port
                    TCP port used for this barrier
            timeout
                    Maximum time to wait for a the barrier to meet
            start
                    Timestamp when we started waiting
            members
                    All members we expect to find in the barrier
            seen
                    Number of clients seen (should be the length of waiting)
            waiting
                    Clients who have checked in and are waiting (master)
            masterid
                    Hostname/IP address + optional tag of selected master
    """

    def __init__(self, hostid, tag, timeout, port=11922):
        self.hostid = hostid
        self.tag = tag
        self.port = port
        self.timeout = timeout
        logging.info("tag=%s port=%d timeout=%d",
                     self.tag, self.port, self.timeout)

        self.seen = 0
        self.waiting = {}


    def get_host_from_id(self, hostid):
        # Remove any trailing local identifier following a #.
        # This allows multiple members per host which is particularly
        # helpful in testing.
        if not hostid.startswith('#'):
            return hostid.split('#')[0]
        else:
            raise error.BarrierError("Invalid Host id: Host Address should "
                               "be specified")


    def update_timeout(self, timeout):
        try:
            if getattr(self, 'start'):
                self.timeout = (time() - self.start) + timeout
        except AttributeError, a:
            self.timeout = timeout


    def remaining(self):
        try:
            if getattr(self, 'start'):
                timeout = self.timeout - (time() - self.start)
                if (timeout <= 0):
                    errmsg = "timeout waiting for barrier: %s" % self.tag
                    logging.error(error)
                    raise error.BarrierError(errmsg)
        except AttributeError, a:
            timeout = self.timeout

        logging.info("seconds remaining: %d", timeout)
        return timeout


    def master_welcome(self, connection):
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
            if self.tag != tag:
                logging.warn("client arriving for the wrong barrier: %s != %s",
                             self.tag, tag)
                client.settimeout(5)
                client.send("!tag")
                client.close()
                return
            elif name in self.waiting:
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
        self.waiting[name] = connection
        self.seen += 1


    def slave_hello(self, connection):
        (client, addr) = connection
        name = None

        client.settimeout(5)
        try:
            client.send(self.tag + " " + self.hostid)

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
        self.waiting[self.hostid] = connection
        self.seen = 1


    def master_release(self):
        # Check everyone is still there, that they have not
        # crashed or disconnected in the meantime.
        allpresent = True
        abort = self.abort
        for name in self.waiting:
            (client, addr) = self.waiting[name]

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
        for name in self.waiting:
            (client, addr) = self.waiting[name]

            client.settimeout(5)
            try:
                client.send(msg)
            except socket.timeout:
                logging.warn("release timeout: %s", name)
                pass

        if abort:
            raise error.BarrierError("Client requested abort")


    def waiting_close(self):
        # Either way, close out all the clients.  If we have
        # not released them then they know to abort.
        for name in self.waiting:
            (client, addr) = self.waiting[name]

            logging.info("closing client: %s", name)

            try:
                client.close()
            except:
                pass


    def run_server(self, is_master):
        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server.bind(('', self.port))
        self.server.listen(10)

        failed = 0
        try:
            while 1:
                try:
                    # Wait for callers welcoming each.
                    self.server.settimeout(self.remaining())
                    connection = self.server.accept()
                    if is_master:
                        self.master_welcome(connection)
                    else:
                        self.slave_hello(connection)
                except socket.timeout:
                    logging.warn("timeout waiting for remaining clients")
                    pass

                if is_master:
                    # Check if everyone is here.
                    logging.info("master seen %d of %d",
                                 self.seen, len(self.members))
                    if self.seen == len(self.members):
                        self.master_release()
                        break
                else:
                    # Check if master connected.
                    if self.seen:
                        logging.info("slave connected to master")
                        self.slave_wait()
                        break

            self.waiting_close()
            self.server.close()
        except:
            self.waiting_close()
            self.server.close()
            raise


    def run_client(self, is_master):
        while self.remaining() > 0:
            try:
                remote = socket.socket(socket.AF_INET,
                        socket.SOCK_STREAM)
                remote.settimeout(30)
                if is_master:
                    # Connect to all slaves.
                    host = self.get_host_from_id(
                            self.members[self.seen])
                    logging.info("calling slave: %s", host)
                    connection = (remote, (host, self.port))
                    remote.connect(connection[1])
                    self.master_welcome(connection)
                else:
                    # Just connect to the master.
                    host = self.get_host_from_id(
                            self.masterid)
                    logging.info("calling master")
                    connection = (remote, (host, self.port))
                    remote.connect(connection[1])
                    self.slave_hello(connection)
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
                             self.seen, len(self.members))
                if self.seen == len(self.members):
                    self.master_release()
                    break
            else:
                # Check if master connected.
                if self.seen:
                    logging.info("slave connected to master")
                    self.slave_wait()
                    break

        self.waiting_close()


    def slave_wait(self):
        remote = self.waiting[self.hostid][0]
        mode = "wait"
        while 1:
            # All control messages are the same size to allow
            # us to split individual messages easily.
            remote.settimeout(self.remaining())
            reply = remote.recv(4)
            if not reply:
                break

            reply = reply.strip("\r\n")
            logging.info("master said: %s", reply)

            mode = reply
            if reply == "ping":
                # Ensure we have sufficient time for the
                # ping/pong/rlse cyle to complete normally.
                self.update_timeout(10 + 10 * len(self.members))

                if self.abort:
                    msg = "abrt"
                else:
                    msg = "pong"
                logging.info(msg)
                remote.settimeout(self.remaining())
                remote.send(msg)

            elif reply == "rlse" or reply == "abrt":
                # Ensure we have sufficient time for the
                # ping/pong/rlse cyle to complete normally.
                self.update_timeout(10 + 10 * len(self.members))

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
            raise error.BarrierError("Client requested abort")
        else:
            raise error.BarrierError("master handshake failure: " + mode)


    def rendezvous(self, *hosts, **dargs):
        # if called with abort=True, this will raise an exception
        # on all the clients.
        self.start = time()
        self.members = list(hosts)
        self.members.sort()
        self.masterid = self.members.pop(0)
        self.abort = dargs.get('abort', False)

        logging.info("masterid: %s", self.masterid)
        if self.abort:
            logging.debug("%s is aborting", self.hostid)
        if not len(self.members):
            logging.info("No other members listed.")
            return
        logging.info("members: %s", ",".join(self.members))

        self.seen = 0
        self.waiting = {}

        # Figure out who is the master in this barrier.
        if self.hostid == self.masterid:
            logging.info("selected as master")
            self.run_server(is_master=True)
        else:
            logging.info("selected as slave")
            self.run_client(is_master=False)


    def rendezvous_servers(self, masterid, *hosts, **dargs):
        # if called with abort=True, this will raise an exception
        # on all the clients.
        self.start = time()
        self.members = list(hosts)
        self.members.sort()
        self.masterid = masterid
        self.abort = dargs.get('abort', False)

        logging.info("masterid: %s", self.masterid)
        if not len(self.members):
            logging.info("No other members listed.")
            return
        logging.info("members: %s", ",".join(self.members))

        self.seen = 0
        self.waiting = {}

        # Figure out who is the master in this barrier.
        if self.hostid == self.masterid:
            logging.info("selected as master")
            self.run_client(is_master=True)
        else:
            logging.info("selected as slave")
            self.run_server(is_master=False)
