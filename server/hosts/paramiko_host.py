import os, sys, time, signal, socket, re, fnmatch, logging, threading
import paramiko

from autotest_lib.client.common_lib import utils, error
from autotest_lib.server import subcommand
from autotest_lib.server.hosts import abstract_ssh


class ParamikoHost(abstract_ssh.AbstractSSHHost):
    KEEPALIVE_TIMEOUT_SECONDS = 30
    CONNECT_TIMEOUT_SECONDS = 30
    CONNECT_TIMEOUT_RETRIES = 3

    def _initialize(self, hostname, *args, **dargs):
        super(ParamikoHost, self)._initialize(hostname=hostname, *args, **dargs)

        # paramiko is very noisy, tone down the logging
        paramiko.util.log_to_file("/dev/null", paramiko.util.ERROR)

        self.keys = self.get_user_keys(hostname)
        self.pid = None


    @staticmethod
    def _load_key(path):
        """Given a path to a private key file, load the appropriate keyfile.

        Tries to load the file as both an RSAKey and a DSAKey. If the file
        cannot be loaded as either type, returns None."""
        try:
            return paramiko.DSSKey.from_private_key_file(path)
        except paramiko.SSHException:
            try:
                return paramiko.RSAKey.from_private_key_file(path)
            except paramiko.SSHException:
                return None


    @staticmethod
    def _parse_config_line(line):
        """Given an ssh config line, return a (key, value) tuple for the
        config value listed in the line, or (None, None)"""
        match = re.match(r"\s*(\w+)\s*=?(.*)\n", line)
        if match:
            return match.groups()
        else:
            return None, None


    @staticmethod
    def get_user_keys(hostname):
        """Returns a mapping of path -> paramiko.PKey entries available for
        this user. Keys are found in the default locations (~/.ssh/id_[d|r]sa)
        as well as any IdentityFile entries in the standard ssh config files.
        """
        raw_identity_files = ["~/.ssh/id_dsa", "~/.ssh/id_rsa"]
        for config_path in ("/etc/ssh/ssh_config", "~/.ssh/config"):
            if not os.path.exists(config_path):
                continue
            host_pattern = "*"
            config_lines = open(os.path.expanduser(config_path)).readlines()
            for line in config_lines:
                key, value = ParamikoHost._parse_config_line(line)
                if key == "Host":
                    host_pattern = value
                elif (key == "IdentityFile"
                      and fnmatch.fnmatch(hostname, host_pattern)):
                    raw_identity_files.append(host_pattern)

        # drop any files that use percent-escapes; we don't support them
        identity_files = []
        UNSUPPORTED_ESCAPES = ["%d", "%u", "%l", "%h", "%r"]
        for path in raw_identity_files:
            # skip this path if it uses % escapes
            if sum((escape in path) for escape in UNSUPPORTED_ESCAPES):
                continue
            path = os.path.expanduser(path)
            if os.path.exists(path):
                identity_files.append(path)

        # load up all the keys that we can and return them
        user_keys = {}
        for path in identity_files:
            key = ParamikoHost._load_key(path)
            if key:
                user_keys[path] = key
        return user_keys


    @staticmethod
    def _check_transport_error(transport):
        error = transport.get_exception()
        if error:
            transport.close()
            raise error


    def _connect_transport(self, pkey):
        for _ in xrange(self.CONNECT_TIMEOUT_RETRIES):
            transport = paramiko.Transport((self.hostname, self.port))
            completed = threading.Event()
            transport.start_client(completed)
            completed.wait(self.CONNECT_TIMEOUT_SECONDS)
            if completed.isSet():
                self._check_transport_error(transport)
                completed.clear()
                transport.auth_publickey(self.user, pkey, completed)
                completed.wait(self.CONNECT_TIMEOUT_SECONDS)
                if completed.isSet():
                    self._check_transport_error(transport)
                    if not transport.is_authenticated():
                        transport.close()
                        raise paramiko.AuthenticationException()
                    return transport
            logging.warn("SSH negotiation (%s:%d) timed out, retrying", 
                         self.hostname, self.port)
            # HACK: we can't count on transport.join not hanging now, either
            transport.join = lambda: None
            transport.close()
        logging.error("SSH negotation (%s:%d) has timed out %s times, "
                      "giving up", self.hostname, self.port, 
                      self.CONNECT_TIMEOUT_RETRIES)
        raise error.AutoservSSHTimeout("SSH negotiation timed out")


    def _init_transport(self):
        for path, key in self.keys.iteritems():
            try:
                logging.debug("Connecting with %s", path)
                transport = self._connect_transport(key)
                transport.set_keepalive(self.KEEPALIVE_TIMEOUT_SECONDS)
                self.transport = transport
                self.pid = os.getpid()
                return
            except paramiko.AuthenticationException:
                logging.debug("Authentication failure")
        else:
            raise error.AutoservSshPermissionDeniedError(
                "Permission denied using all keys available to ParamikoHost",
                utils.CmdResult())


    def _open_channel(self, timeout):
        start_time = time.time()
        if os.getpid() != self.pid:
            if self.pid is not None:
                # HACK: paramiko tries to join() on its worker thread
                # and this just hangs on linux after a fork()
                self.transport.join = lambda: None
                self.transport.atfork()
                join_hook = lambda cmd: self._close_transport()
                subcommand.subcommand.register_join_hook(join_hook)
                logging.debug("Reopening SSH connection after a process fork")
            self._init_transport()

        channel = None
        try:
            channel = self.transport.open_session()
        except (socket.error, paramiko.SSHException, EOFError), e:
            logging.warn("Exception occured while opening session: %s", e)
            if time.time() - start_time >= timeout:
                raise error.AutoservSSHTimeout("ssh failed: %s" % e)

        if not channel:
            # we couldn't get a channel; re-initing transport should fix that
            try:
                self.transport.close()
            except Exception, e:
                logging.debug("paramiko.Transport.close failed with %s", e)
            self._init_transport()
            return self.transport.open_session()
        else:
            return channel


    def _close_transport(self):
        if os.getpid() == self.pid:
            self.transport.close()


    def close(self):
        super(ParamikoHost, self).close()
        self._close_transport()


    @staticmethod
    def _exhaust_stream(tee, output_list, recvfunc):
        while True:
            try:
                output_list.append(recvfunc(2**16))
            except socket.timeout:
                return
            tee.write(output_list[-1])
            if not output_list[-1]:
                return


    def run(self, command, timeout=3600, ignore_status=False,
            stdout_tee=utils.TEE_TO_LOGS, stderr_tee=utils.TEE_TO_LOGS,
            connect_timeout=30, verbose=True):
        """
        Run a command on the remote host.
        @see common_lib.hosts.host.run()

        @param connect_timeout: connection timeout (in seconds)
        @param options: string with additional ssh command options
        @param verbose: log the commands

        @raises AutoservRunError: if the command failed
        @raises AutoservSSHTimeout: ssh connection has timed out
        """

        stdout = utils.get_stream_tee_file(
                stdout_tee, utils.DEFAULT_STDOUT_LEVEL)
        stderr = utils.get_stream_tee_file(
                stderr_tee, utils.get_stderr_level(ignore_status))

        if verbose:
            logging.debug("Running (ssh-paramiko) '%s'" % command)

        # start up the command
        start_time = time.time()
        try:
            channel = self._open_channel(timeout)
            channel.exec_command(command)
        except (socket.error, paramiko.SSHException), e:
            # This has to match the string from paramiko *exactly*.
            if str(e) != 'Channel closed.':
                raise error.AutoservSSHTimeout("ssh failed: %s" % e)

        # pull in all the stdout, stderr until the command terminates
        raw_stdout, raw_stderr = [], []
        timed_out = False
        while not channel.exit_status_ready():
            if channel.recv_ready():
                raw_stdout.append(channel.recv(2**16))
                stdout.write(raw_stdout[-1])
            if channel.recv_stderr_ready():
                raw_stderr.append(channel.recv_stderr(2**16))
                stderr.write(raw_stderr[-1])
            if timeout and time.time() - start_time > timeout:
                timed_out = True
                break
            time.sleep(1)
        if timed_out:
            exit_status = -signal.SIGTERM
        else:
            exit_status = channel.recv_exit_status()
        channel.settimeout(10)
        self._exhaust_stream(stdout, raw_stdout, channel.recv)
        self._exhaust_stream(stderr, raw_stderr, channel.recv_stderr)
        channel.close()
        duration = time.time() - start_time

        # create the appropriate results
        stdout = "".join(raw_stdout)
        stderr = "".join(raw_stderr)
        result = utils.CmdResult(command, stdout, stderr, exit_status,
                                 duration)
        if exit_status == -signal.SIGHUP:
            msg = "ssh connection unexpectedly terminated"
            raise error.AutoservRunError(msg, result)
        if not ignore_status and exit_status:
            raise error.AutoservRunError(command, result)
        return result
