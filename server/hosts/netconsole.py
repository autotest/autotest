import os, re, sys, subprocess, socket

from autotest_lib.client.common_lib import utils, error
from autotest_lib.server.hosts import remote


class NetconsoleHost(remote.RemoteHost):
    def _initialize(self, console_log="netconsole.log", *args, **dargs):
        super(NetconsoleHost, self)._initialize(*args, **dargs)

        self.__logger = None
        self.__console_log = console_log

        # get a socket for us to listen on
        self.__socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.__socket.bind(('', 0))
        self.__port = self.__socket.getsockname()[1]


    @classmethod
    def host_is_supported(cls, run_func):
        local_ip = socket.gethostbyname(socket.gethostname())
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(1)
        s.bind((local_ip, 0))
        local_port = s.getsockname()[1]
        send_udp_packet = (
            """python -c "from socket import *; """
            """s = socket(AF_INET, SOCK_DGRAM); """
            """s.sendto('ping', ('%s', %d))" """ % (local_ip, local_port))
        run_func(send_udp_packet)
        try:
            msg = s.recv(4)
        except Exception:
            supported = False
        else:
            supported = (msg == "ping")
        s.close()
        return supported


    def start_loggers(self):
        super(NetconsoleHost, self).start_loggers()

        if not self.__console_log:
            return

        self.__netconsole_params = self.__determine_netconsole_params()
        if self.__netconsole_params is None:
            return

        r, w = os.pipe()
        script_path = os.path.join(self.monitordir, "console.py")
        cmd = [sys.executable, script_path, self.__console_log, str(w)]

        self.__warning_stream = os.fdopen(r, "r", 0)
        if self.job:
            self.job.warning_loggers.add(self.__warning_stream)

        stdin = self.__socket.fileno()
        stdout = stderr = open(os.devnull, "w")
        self.__logger = subprocess.Popen(cmd, stdin=stdin, stdout=stdout,
                                         stderr=stderr)
        os.close(w)

        self.__unload_netconsole_module()
        self.__load_netconsole_module()


    def stop_loggers(self):
        super(NetconsoleHost, self).stop_loggers()

        if self.__logger:
            utils.nuke_subprocess(self.__logger)
            self.__logger = None
            if self.job:
                self.job.warning_loggers.discard(self.__warning_stream)
            self.__warning_stream.close()


    def reboot_setup(self, *args, **dargs):
        super(NetconsoleHost, self).reboot_setup(*args, **dargs)

        if self.__netconsole_params is not None:
            label = dargs.get("label", None)
            if not label:
                label = self.bootloader.get_default_title()
            args = "debug " + self.__netconsole_params
            self.bootloader.add_args(label, args)
        self.__unload_netconsole_module()


    def reboot_followup(self, *args, **dargs):
        super(NetconsoleHost, self).reboot_followup(*args, **dargs)
        self.__load_netconsole_module()


    def __determine_netconsole_params(self):
        """
        Connect to the remote machine and determine the values to use for the
        required netconsole parameters.
        """
        # determine the IP addresses of the local and remote machine
        # PROBLEM: on machines with multiple IPs this may not make any sense
        # It also doesn't work with IPv6
        remote_ip = socket.gethostbyname(self.hostname)
        local_ip = socket.gethostbyname(socket.gethostname())

        # Get the gateway of the remote machine
        try:
            traceroute = self.run('traceroute -n %s' % local_ip)
        except error.AutoservRunError:
            return
        first_node = traceroute.stdout.split("\n")[0]
        match = re.search(r'\s+((\d+\.){3}\d+)\s+', first_node)
        if match:
            router_ip = match.group(1)
        else:
            return

        # Look up the MAC address of the gateway
        try:
            self.run('ping -c 1 %s' % router_ip)
            arp = self.run('arp -n -a %s' % router_ip)
        except error.AutoservRunError:
            return
        match = re.search(r'\s+(([0-9A-F]{2}:){5}[0-9A-F]{2})\s+', arp.stdout)
        if match:
            gateway_mac = match.group(1)
        else:
            return None

        return 'netconsole=@%s/,%s@%s/%s' % (remote_ip, self.__port, local_ip,
                                             gateway_mac)


    def __load_netconsole_module(self):
        """
        Make a best effort to load the netconsole module.

        Note that loading the module can fail even when the remote machine is
        working correctly if netconsole is already compiled into the kernel
        and started.
        """
        if self.__netconsole_params is None:
            return

        try:
            self.run('dmesg -n 8')
            self.run('modprobe netconsole %s' % self.__netconsole_params)
        except error.AutoservRunError, e:
            # if it fails there isn't much we can do, just keep going
            print "ERROR occured while loading netconsole: %s" % e


    def __unload_netconsole_module(self):
        try:
            self.run('modprobe -r netconsole')
        except error.AutoservRunError:
            pass
