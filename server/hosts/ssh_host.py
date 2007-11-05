#!/usr/bin/python
#
# Copyright 2007 Google Inc. Released under the GPL v2

"""
This module defines the SSHHost class.

Implementation details:
You should import the "hosts" package instead of importing each type of host.

	SSHHost: a remote machine with a ssh access
"""

__author__ = """
mbligh@google.com (Martin J. Bligh),
poirier@google.com (Benjamin Poirier),
stutsman@google.com (Ryan Stutsman)
"""


import types, os, sys, signal, subprocess, time, re, socket
import base_classes, utils, errors, bootloader


class SSHHost(base_classes.RemoteHost):
	"""
	This class represents a remote machine controlled through an ssh 
	session on which you can run programs.

	It is not the machine autoserv is running on. The machine must be 
	configured for password-less login, for example through public key 
	authentication.

	It includes support for controlling the machine through a serial
	console on which you can run programs. If such a serial console is
	set up on the machine then capabilities such as hard reset and
	boot strap monitoring are available. If the machine does not have a
	serial console available then ordinary SSH-based commands will
	still be available, but attempts to use extensions such as
	console logging or hard reset will fail silently.

	Implementation details:
	This is a leaf class in an abstract class hierarchy, it must 
	implement the unimplemented methods in parent classes.
	"""

	SSH_BASE_COMMAND = '/usr/bin/ssh -a -o BatchMode=yes'
	DEFAULT_REBOOT_TIMEOUT = 1800
	job = None

	def __init__(self, hostname, user="root", port=22, initialize=True,
		     conmux_log="console.log", conmux_warnings="status.log",
		     conmux_server=None, conmux_attach=None,
		     netconsole_log=None, netconsole_port=6666):
		"""
		Construct a SSHHost object
		
		Args:
			hostname: network hostname or address of remote machine
			user: user to log in as on the remote machine
			port: port the ssh daemon is listening on on the remote 
				machine
		""" 
		self.hostname= hostname
		self.user= user
		self.port= port
		self.tmp_dirs= []
		self.initialize = initialize

		super(SSHHost, self).__init__()

		self.conmux_server = conmux_server
		self.conmux_attach = self.__find_console_attach(conmux_attach)
		self.logger_pid = None
		self.__start_console_log(conmux_log)
		self.warning_pid = None
		self.__start_warning_log(conmux_warnings)

		self.bootloader = bootloader.Bootloader(self)

		self.__netconsole_param = ""
		self.netlogger_pid = None
		if netconsole_log:
			self.__init_netconsole_params(netconsole_port)
			self.__start_netconsole_log(netconsole_log, netconsole_port)
			self.__load_netconsole_module()


	def __del__(self):
		"""
		Destroy a SSHHost object
		"""
		for dir in self.tmp_dirs:
			try:
				self.run('rm -rf "%s"' % (utils.sh_escape(dir)))
			except errors.AutoservRunError:
				pass
		# kill the console logger
		if getattr(self, 'logger_pid', None):
			try:
				pgid = os.getpgid(self.logger_pid)
				os.killpg(pgid, signal.SIGTERM)
			except OSError:
				pass
		# kill the netconsole logger
		if getattr(self, 'netlogger_pid', None):
			self.__unload_netconsole_module()
			try:
				os.kill(self.netlogger_pid, signal.SIGTERM)
			except OSError:
				pass
		# kill the warning logger
		if getattr(self, 'warning_pid', None):
			try:
				pgid = os.getpgid(self.warning_pid)
				os.killpg(pgid, signal.SIGTERM)
			except OSError:
				pass


	def __init_netconsole_params(self, port):
		"""
		Connect to the remote machine and determine the values to use for the
		required netconsole parameters.
		"""
		# PROBLEM: on machines with multiple IPs this may not make any sense
		# It also doesn't work with IPv6
		remote_ip = socket.gethostbyname(self.hostname)
		local_ip = socket.gethostbyname(socket.gethostname())
		# Get the gateway of the remote machine
		try:
			traceroute = self.run('traceroute -n %s' % local_ip)
		except errors.AutoservRunError:
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
		except errors.AutoservRunError:
			return
		match = re.search(r'\s+(([0-9A-F]{2}:){5}[0-9A-F]{2})\s+', arp.stdout)
		if match:
			gateway_mac = match.group(1)
		else:
			return
		self.__netconsole_param = 'netconsole=@%s/,%s@%s/%s' % (remote_ip,
									port,
									local_ip,
									gateway_mac)


	def __start_netconsole_log(self, logfilename, port):
		"""
		Log the output of netconsole to a specified file
		"""
		if logfilename == None:
			return
		cmd = ['nc', '-u', '-l', '-p', str(port)]
		logger = subprocess.Popen(cmd, stdout=open(logfilename, "a", 0))
		self.netlogger_pid = logger.pid


	def __load_netconsole_module(self):
		"""
		Make a best effort to load the netconsole module.

		Note that loading the module can fail even when the remote machine is
		working correctly if netconsole is already compiled into the kernel
		and started.
		"""
		if not self.__netconsole_param:
			return
		try:
			self.run('modprobe netconsole %s' % self.__netconsole_param)
		except errors.AutoservRunError:
			# if it fails there isn't much we can do, just keep going
			pass


	def __unload_netconsole_module(self):
		try:
			self.run('modprobe -r netconsole')
		except errors.AutoservRunError:
			pass


	def _wait_for_restart(self, timeout):
		if not self.wait_down(300):	# Make sure he's dead, Jim
			self.__record("ABORT", None, "reboot.verify")
			raise errors.AutoservRebootError("Host did not shut down")
		self.wait_up(timeout)
		time.sleep(2) # this is needed for complete reliability
		if self.wait_up(timeout):
			self.__record("GOOD", None, "reboot.verify")
		else:
			self.__record("ABORT", None, "reboot.verify")
			raise errors.AutoservRebootError("Host did not return from reboot")
		print "Reboot complete"


	def hardreset(self, timeout=DEFAULT_REBOOT_TIMEOUT, wait=True):
		"""
		Reach out and slap the box in the power switch
		"""
		command_ran = self.__console_run(r"'~$hardreset'")
                if not command_ran:
                        raise errors.AutoservUnsupportedError
                if wait:
                        self._wait_for_restart(timeout)


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
		cmd = [self.conmux_attach, self.__conmux_hostname(), 'cat - >> %s' % logfilename]
		logger = subprocess.Popen(cmd,
					  stderr=open('/dev/null', 'w'),
					  preexec_fn=lambda: os.setpgid(0, 0))
		self.logger_pid = logger.pid


        def __start_warning_log(self, logfilename):
		"""
		Log the output of the warning monitor to a specified file
		"""
		if logfilename == None:
			return
		script_path = os.path.join(self.serverdir, 'warning_monitor')
		script_cmd = 'expect %s %s >> %s' % (script_path,
						     self.hostname,
						     logfilename)
		if self.conmux_server:
			to = '%s/%s'
		cmd = [self.conmux_attach, self.__conmux_hostname(), script_cmd]
		logger = subprocess.Popen(cmd,
					  stderr=open('debug/conmux.log', 'a', 0),
					  preexec_fn=lambda: os.setpgid(0, 0))
		self.warning_pid = logger.pid


	def __find_console_attach(self, conmux_attach):
		if conmux_attach:
			return conmux_attach
		try:
			res = utils.run('which conmux-attach')
			if res.exit_status == 0:
				return res.stdout.strip()
		except errors.AutoservRunError, e:
			pass
		autotest_conmux = os.path.join(self.serverdir, '..',
					       'conmux', 'conmux-attach')
		autotest_conmux_alt = os.path.join(self.serverdir,
						   '..', 'autotest',
						   'conmux', 'conmux-attach')
		locations = [autotest_conmux,
			     autotest_conmux_alt,
			     '/usr/local/conmux/bin/conmux-attach',
			     '/usr/bin/conmux-attach']
		for l in locations:
			if os.path.exists(l):
				return l

		print "WARNING: conmux-attach not found on autoserv server"
		return None


	def __console_run(self, cmd):
		"""
		Send a command to the conmux session
		"""
		if not self.conmux_attach or not os.path.exists(self.conmux_attach):
			return False
		cmd = '%s %s echo %s 2> /dev/null' % (self.conmux_attach,
						      self.__conmux_hostname(),
						      cmd)
		result = os.system(cmd)
		return result == 0


	def __record(self, status_code, subdir, operation, status = ''):
		if self.job:
			self.job.record(status_code, subdir, operation, status)
		else:
			if not subdir:
				subdir = "----"
			msg = "%s\t%s\t%s\t%s" % (status_code, subdir, operation, status)
			sys.stderr.write(msg + "\n")


	def ssh_command(self):
		"""Construct an ssh command with proper args for this host."""
		return r'%s -l %s -p %d %s' % (self.SSH_BASE_COMMAND,
					       self.user,
					       self.port,
					       self.hostname)


	def run(self, command, timeout=None, ignore_status=False):
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
			a hosts.base_classes.CmdResult object
		
		Raises:
			AutoservRunError: the exit code of the command 
				execution was not 0
		"""
		#~ print "running %s" % (command,)
		result= utils.run(r'%s "%s"' % (self.ssh_command(),
						utils.sh_escape(command)),
				  timeout, ignore_status)
		return result


	def reboot(self, timeout=DEFAULT_REBOOT_TIMEOUT, label=None,
		   kernel_args=None, wait=True):
		"""
		Reboot the remote host.
		
		Args:
			timeout
		"""
		# forcibly include the "netconsole" kernel arg
		if self.__netconsole_param:
			if kernel_args is None:
				kernel_args = self.__netconsole_param
			else:
				kernel_args += " " + self.__netconsole_param
			# unload the (possibly loaded) module to avoid shutdown issues
			self.__unload_netconsole_module()
		if label or kernel_args:
			self.bootloader.install_boottool()
		if label:
			self.bootloader.set_default(label)
		if kernel_args:
			if not label:
				default = int(self.bootloader.get_default())
				label = self.bootloader.get_titles()[default]
			self.bootloader.add_args(label, kernel_args)
		print "Reboot: initiating reboot"
		self.__record("GOOD", None, "reboot.start")
		try:
			self.run('(sleep 5; reboot) >/dev/null 2>&1 &')
		except AutoservRunError:
			self.__record("ABORT", None, "reboot.start")
			raise
		if wait:
			self._wait_for_restart(timeout)
			self.__load_netconsole_module() # if the builtin fails


	def get_file(self, source, dest):
		"""
		Copy files from the remote host to a local path.
		
		Directories will be copied recursively.
		If a source component is a directory with a trailing slash, 
		the content of the directory will be copied, otherwise, the 
		directory itself and its content will be copied. This 
		behavior is similar to that of the program 'rsync'.
		
		Args:
			source: either
				1) a single file or directory, as a string
				2) a list of one or more (possibly mixed) 
					files or directories
			dest: a file or a directory (if source contains a 
				directory or more than one element, you must 
				supply a directory dest)
		
		Raises:
			AutoservRunError: the scp command failed
		"""
		if isinstance(source, types.StringTypes):
			source= [source]
		
		processed_source= []
		for entry in source:
			if entry.endswith('/'):
				format_string= '%s@%s:"%s*"'
			else:
				format_string= '%s@%s:"%s"'
			entry= format_string % (self.user, self.hostname, 
				utils.scp_remote_escape(entry))
			processed_source.append(entry)
		
		processed_dest= os.path.abspath(dest)
		if os.path.isdir(dest):
			processed_dest= "%s/" % (utils.sh_escape(processed_dest),)
		else:
			processed_dest= utils.sh_escape(processed_dest)
		
		utils.run('scp -rpq %s "%s"' % (
			" ".join(processed_source), 
			processed_dest))


	def send_file(self, source, dest):
		"""
		Copy files from a local path to the remote host.
		
		Directories will be copied recursively.
		If a source component is a directory with a trailing slash, 
		the content of the directory will be copied, otherwise, the 
		directory itself and its content will be copied. This 
		behavior is similar to that of the program 'rsync'.
		
		Args:
			source: either
				1) a single file or directory, as a string
				2) a list of one or more (possibly mixed) 
					files or directories
			dest: a file or a directory (if source contains a 
				directory or more than one element, you must 
				supply a directory dest)
		
		Raises:
			AutoservRunError: the scp command failed
		"""
		if isinstance(source, types.StringTypes):
			source= [source]
		
		processed_source= []
		for entry in source:
			if entry.endswith('/'):
				format_string= '"%s/"*'
			else:
				format_string= '"%s"'
			entry= format_string % (utils.sh_escape(os.path.abspath(entry)),)
			processed_source.append(entry)

			result = utils.run(r'%s rsync -h' % self.ssh_command(),
					   ignore_status=True)

		remote_dest = '%s@%s:"%s"' % (
			    self.user, self.hostname,
			    utils.scp_remote_escape(dest))
		if result.exit_status == 0:
			utils.run('rsync --rsh="%s" -az %s %s' % (
			    self.SSH_BASE_COMMAND, " ".join(processed_source),
			    remote_dest))
		else:
			utils.run('scp -rpq %s %s' % (
			    " ".join(processed_source),
			    remote_dest))
		self.run('find "%s" -type d | xargs -r chmod o+rx' % dest)
		self.run('find "%s" -type f | xargs -r chmod o+r' % dest)

	def get_tmp_dir(self):
		"""
		Return the pathname of a directory on the host suitable 
		for temporary file storage.
		
		The directory and its content will be deleted automatically
		on the destruction of the Host object that was used to obtain
		it.
		"""
		dir_name= self.run("mktemp -d /tmp/autoserv-XXXXXX").stdout.rstrip(" \n")
		self.tmp_dirs.append(dir_name)
		return dir_name


	def is_up(self):
		"""
		Check if the remote host is up.
		
		Returns:
			True if the remote host is up, False otherwise
		"""
		try:
			result= self.run("true", timeout=10)
		except errors.AutoservRunError:
			return False
		else:
			if result.exit_status == 0:
				return True
			else:

				return False

	def wait_up(self, timeout=None):
		"""
		Wait until the remote host is up or the timeout expires.
		
		In fact, it will wait until an ssh connection to the remote 
		host can be established.
		
		Args:
			timeout: time limit in seconds before returning even
				if the host is not up.
		
		Returns:
			True if the host was found to be up, False otherwise
		"""
		if timeout:
			end_time= time.time() + timeout
		
		while not timeout or time.time() < end_time:
			try:
				run_timeout= 10
				result= self.run("true", timeout=run_timeout)
			except errors.AutoservRunError:
				pass
			else:
				if result.exit_status == 0:
					return True
			time.sleep(1)
		
		return False


	def wait_down(self, timeout=None):
		"""
		Wait until the remote host is down or the timeout expires.
		
		In fact, it will wait until an ssh connection to the remote 
		host fails.
		
		Args:
			timeout: time limit in seconds before returning even
				if the host is not up.
		
		Returns:
			True if the host was found to be down, False otherwise
		"""
		if timeout:
			end_time= time.time() + timeout
		
		while not timeout or time.time() < end_time:
			try:
				run_timeout= 10
				result= self.run("true", timeout=run_timeout)
			except errors.AutoservRunError:
				return True
			else:
				if result.aborted:
					return True
			time.sleep(1)
		
		return False


	def ensure_up(self):
		"""
		Ensure the host is up if it is not then do not proceed;
		this prevents cacading failures of tests
		"""
		print 'Ensuring that %s is up before continuing' % self.hostname
		if hasattr(self, 'hardreset') and not self.wait_up(300):
			print "Performing a hardreset on %s" % self.hostname
			self.hardreset()
		if not self.wait_up(60 * 30):
			# 30 minutes should be more than enough
			raise errors.AutoservHostError
		print 'Host up, continuing'


	def get_num_cpu(self):
		"""
		Get the number of CPUs in the host according to 
		/proc/cpuinfo.
		
		Returns:
			The number of CPUs
		"""
		
		proc_cpuinfo = self.run("cat /proc/cpuinfo").stdout
		cpus = 0
		for line in proc_cpuinfo.splitlines():
			if line.startswith('processor'):
				cpus += 1
		return cpus


	def check_uptime(self):
		"""
		Check that uptime is available and monotonically increasing.
		"""
		if not self.ping():
			raise "Client is not pingable"
		result = self.run("/bin/cat /proc/uptime", 30)
		return result.stdout.strip().split()[0]


	def get_arch(self):
		"""
		Get the hardware architecture of the remote machine
		"""
		arch = self.run('/bin/uname -m').stdout.rstrip()
		if re.match(r'i\d86$', arch):
			arch = 'i386'
		return arch


	def get_kernel_ver(self):
		"""
		Get the kernel version of the remote machine
		"""
		return self.run('/bin/uname -r').stdout.rstrip()


	def get_cmdline(self):
		"""
		Get the kernel command line of the remote machine
		"""
		return self.run('cat /proc/cmdline').stdout.rstrip()


	def ping(self):
		"""
		Ping the remote system, and return whether it's available
		"""
		fpingcmd = "%s -q %s" % ('/usr/bin/fping', self.hostname)
		rc = utils.system(fpingcmd, ignore_status = 1)
		return (rc == 0)


	def ssh_ping(self):
		self.run('ls', timeout=30)
