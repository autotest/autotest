import os, sys, subprocess

from autotest_lib.client.common_lib import utils
from autotest_lib.server.hosts import site_host


class SerialHost(site_host.SiteHost):
    def __init__(self, conmux_server=None, conmux_attach=None,
                 conmux_log="console.log", *args, **dargs):
        super(SerialHost, self).__init__(*args, **dargs)

        self.conmux_server = conmux_server
        if conmux_attach:
            self.conmux_attach = conmux_attach
        else:
            self.conmux_attach = os.path.abspath(os.path.join(
                self.serverdir, '..', 'conmux', 'conmux-attach'))

        self.logger_popen = None
        self.warning_stream = None
        self.__start_console_log(conmux_log)


    def __del__(self):
        self.__stop_console_log()


    def __conmux_hostname(self):
        if self.conmux_server:
            return '%s/%s' % (self.conmux_server, self.hostname)
        else:
            return self.hostname


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
        cmd = [self.conmux_attach, self.__conmux_hostname(),
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
                                              self.__conmux_hostname(),
                                              cmd)
        result = utils.system(cmd, ignore_status=True)
        return result == 0
