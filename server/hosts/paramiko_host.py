import os, sys, time, signal, socket
import paramiko

from autotest_lib.client.common_lib import utils, error, debug
from autotest_lib.server.hosts import abstract_ssh


class ParamikoHost(abstract_ssh.AbstractSSHHost):
    def __init__(self, hostname, *args, **dargs):
        super(ParamikoHost, self).__init__(hostname=hostname, *args, **dargs)

        # paramiko is very noisy, tone down the logging
        paramiko.util.log_to_file("/dev/null", paramiko.util.ERROR)

        self.key = self._get_user_key()
        assert self.key is not None
        self.pid = None

        self.host_log = debug.get_logger()

        self.start_loggers()


    def _get_user_key(self):
        # try the dsa key first
        keyfile = os.path.expanduser("~/.ssh/id_dsa")
        if os.path.exists(keyfile):
            return paramiko.DSSKey.from_private_key_file(keyfile)

        # try the rsa key instead
        keyfile = os.path.expanduser("~/.ssh/id_rsa")
        if os.path.exists(keyfile):
            return paramiko.RSAKey.from_private_key_file(keyfile)

        return None


    def _init_transport(self):
        transport = paramiko.Transport((self.hostname, self.port))
        transport.connect(username=self.user, pkey=self.key)
        self.transport = transport
        self.pid = os.getpid()


    def _open_channel(self):
        if os.getpid() != self.pid:
            # initialize the transport for the first time, or after a fork
            self._init_transport()
        try:
            return self.transport.open_session()
        except (socket.error, paramiko.SSHException):
            # we couldn't open a channel, try re-initializing the transport
            self._init_transport()
            return self.transport.open_session()


    @staticmethod
    def _exhaust_stream(tee, output_list, recvfunc):
        while True:
            output_list.append(recvfunc(2**16))
            tee.write(output_list[-1])
            if not output_list[-1]:
                return


    def run(self, command, timeout=3600, ignore_status=False,
            stdout_tee=None, stderr_tee=None, connect_timeout=30):
        """
        Run a command on the remote host.

        Args:
            command: the command line string
            timeout: time limit in seconds before attempting to
                     kill the running process. The run() function
                     will take a few seconds longer than 'timeout'
                     to complete if it has to kill the process.
            ignore_status: do not raise an exception, no matter
                           what the exit code of the command is.

        Returns:
            a utils.CmdResult object

        Raises:
            AutoservRunError: the exit code of the command
                              execution was not 0
            AutoservSSHTimeout: ssh connection has timed out
        """

        # tee to std* if no tees are provided
        stdout = stdout_tee or sys.stdout
        stderr = stderr_tee or sys.stderr
        self.host_log.debug("ssh-paramiko: %s" % command)

        # start up the command
        echo_cmd = "echo `date '+%m/%d/%y %H:%M:%S'` Connected. >&2"
        full_cmd = "%s;%s" % (echo_cmd, command)
        start_time = time.time()
        try:
            channel = self._open_channel()
            channel.exec_command(full_cmd)
        except (socket.error, paramiko.SSHException), e:
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
                channel.close()
                break
            time.sleep(1)
        if timed_out:
            exit_status = -signal.SIGTERM
        else:
            exit_status = channel.recv_exit_status()
        self._exhaust_stream(stdout, raw_stdout, channel.recv)
        self._exhaust_stream(stderr, raw_stderr, channel.recv_stderr)
        duration = time.time() - start_time

        # create the appropriate results
        stdout = "".join(raw_stdout)
        stderr = "".join(raw_stderr)
        result = utils.CmdResult(command, stdout, stderr, exit_status,
                                 duration)
        if not ignore_status and exit_status:
            raise error.AutoservRunError(command, result)
        return result
