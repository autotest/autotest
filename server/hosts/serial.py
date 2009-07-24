import os, sys, subprocess, logging

from autotest_lib.client.common_lib import utils, error
from autotest_lib.server import utils as server_utils
from autotest_lib.server.hosts import remote


SiteHost = utils.import_site_class(
    __file__, "autotest_lib.server.hosts.site_host", "SiteHost",
    remote.RemoteHost)


class SerialHost(SiteHost):
    DEFAULT_REBOOT_TIMEOUT = SiteHost.DEFAULT_REBOOT_TIMEOUT

    def _initialize(self, conmux_server=None, conmux_attach=None,
                    console_log="console.log", *args, **dargs):
        super(SerialHost, self)._initialize(*args, **dargs)

        self.__logger = None
        self.__console_log = console_log

        self.conmux_server = conmux_server
        self.conmux_attach = self._get_conmux_attach(conmux_attach)


    @classmethod
    def _get_conmux_attach(cls, conmux_attach=None):
        if conmux_attach:
            return conmux_attach

        # assume we're using the conmux-attach provided with autotest
        server_dir = server_utils.get_server_dir()
        path = os.path.join(server_dir, "..", "conmux", "conmux-attach")
        path = os.path.abspath(path)
        return path


    @staticmethod
    def _get_conmux_hostname(hostname, conmux_server):
        if conmux_server:
            return "%s/%s" % (conmux_server, hostname)
        else:
            return hostname


    def get_conmux_hostname(self):
        return self._get_conmux_hostname(self.hostname, self.conmux_server)


    @classmethod
    def host_is_supported(cls, hostname, conmux_server=None,
                          conmux_attach=None):
        """ Returns a boolean indicating if the remote host with "hostname"
        supports use as a SerialHost """
        conmux_attach = cls._get_conmux_attach(conmux_attach)
        conmux_hostname = cls._get_conmux_hostname(hostname, conmux_server)
        cmd = "%s %s echo 2> /dev/null" % (conmux_attach, conmux_hostname)
        try:
            result = utils.run(cmd, ignore_status=True, timeout=10)
            return result.exit_status == 0
        except error.CmdError:
            logging.warning("Timed out while trying to attach to conmux")

        return False


    def start_loggers(self):
        super(SerialHost, self).start_loggers()

        if self.__console_log is None:
            return

        if not self.conmux_attach or not os.path.exists(self.conmux_attach):
            return

        r, w = os.pipe()
        script_path = os.path.join(self.monitordir, 'console.py')
        cmd = [self.conmux_attach, self.get_conmux_hostname(),
               '%s %s %s %d' % (sys.executable, script_path,
                                self.__console_log, w)]

        self.__warning_stream = os.fdopen(r, 'r', 0)
        if self.job:
            self.job.warning_loggers.add(self.__warning_stream)

        stdout = stderr = open(os.devnull, 'w')
        self.__logger = subprocess.Popen(cmd, stdout=stdout, stderr=stderr)
        os.close(w)


    def stop_loggers(self):
        super(SerialHost, self).stop_loggers()

        if self.__logger:
            utils.nuke_subprocess(self.__logger)
            self.__logger = None
            if self.job:
                self.job.warning_loggers.discard(self.__warning_stream)
            self.__warning_stream.close()


    def run_conmux(self, cmd):
        """
        Send a command to the conmux session
        """
        if not self.conmux_attach or not os.path.exists(self.conmux_attach):
            return False
        cmd = '%s %s echo %s 2> /dev/null' % (self.conmux_attach,
                                              self.get_conmux_hostname(),
                                              cmd)
        result = utils.system(cmd, ignore_status=True)
        return result == 0


    def hardreset(self, timeout=DEFAULT_REBOOT_TIMEOUT, wait=True,
                  conmux_command='hardreset', num_attempts=1):
        """
        Reach out and slap the box in the power switch.
        Args:
                conmux_command: The command to run via the conmux interface
                timeout: timelimit in seconds before the machine is
                considered unreachable
                wait: Whether or not to wait for the machine to reboot

        """
        conmux_command = "'~$%s'" % conmux_command
        def reboot():
            if not self.run_conmux(conmux_command):
                self.record("ABORT", None, "reboot.start",
                            "hard reset unavailable")
                raise error.AutoservUnsupportedError(
                    'Hard reset unavailable')
            self.record("GOOD", None, "reboot.start", "hard reset")
            if wait:
                for _ in xrange(num_attempts):
                    try:
                        self.wait_for_restart(timeout)
                    except error.AutoservShutdownError:
                        msg = "Serial console failed to respond to hard reset"
                        logging.warning(msg)
                    else:
                        break
                else:
                    msg = "Host did not shutdown"
                    raise error.AutoservShutdownError(msg)

        if self.job:
            self.job.disable_warnings("POWER_FAILURE")
        try:
            if wait:
                self.log_reboot(reboot)
            else:
                reboot()
        finally:
            if self.job:
                self.job.enable_warnings("POWER_FAILURE")
