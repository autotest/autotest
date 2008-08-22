import os, sys, subprocess

from autotest_lib.client.common_lib import utils, error
from autotest_lib.server import utils as server_utils
from autotest_lib.server.hosts import site_host


class SerialHost(site_host.SiteHost):
    DEFAULT_REBOOT_TIMEOUT = site_host.SiteHost.DEFAULT_REBOOT_TIMEOUT

    def __init__(self, conmux_server=None, conmux_attach=None,
                 conmux_log="console.log", *args, **dargs):
        super(SerialHost, self).__init__(*args, **dargs)

        self.conmux_server = conmux_server
        self.conmux_attach = self._get_conmux_attach(conmux_attach)

        self.logger_popen = None
        self.warning_stream = None
        self.__start_console_log(conmux_log)


    def __del__(self):
        super(SerialHost, self).__del__()
        self.__stop_console_log()


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
        result = utils.run(cmd)
        return result.exit_status == 0


    def __start_console_log(self, logfilename):
        """
        Log the output of the console session to a specified file
        """
        if logfilename == None:
            return
        if not self.conmux_attach or not os.path.exists(self.conmux_attach):
            return

        r, w = os.pipe()
        script_path = os.path.join(self.serverdir,
                                   'warning_monitor.py')
        cmd = [self.conmux_attach, self.get_conmux_hostname(),
               '%s %s %s %d' % (sys.executable, script_path,
                                logfilename, w)]
        dev_null = open(os.devnull, 'w')

        self.warning_stream = os.fdopen(r, 'r', 0)
        if self.job:
            self.job.warning_loggers.add(self.warning_stream)
        self.logger_popen = subprocess.Popen(cmd, stderr=dev_null)
        os.close(w)


    def __stop_console_log(self):
        if getattr(self, 'logger_popen', None):
            utils.nuke_subprocess(self.logger_popen)
            if self.job:
                self.job.warning_loggers.discard(self.warning_stream)
            self.warning_stream.close()


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
                  conmux_command='hardreset'):
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
                self.wait_for_restart(timeout)

        if wait:
            self.log_reboot(reboot)
        else:
            reboot()
