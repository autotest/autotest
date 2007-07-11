#!/usr/bin/python
#
# Copyright 2007 Google Inc. Released under the GPL v2

"""This module defines the ConmuxSSHHost

Implementation details:
You should import the "hosts" package instead of importing each type of host.

	ConmuxSSHHost: a remote machine controlled through a serial console
"""

__author__ = """mbligh@google.com (Martin J. Bligh),
poirier@google.com (Benjamin Poirier),
stutsman@google.com (Ryan Stutsman)"""

import os
import os.path
import signal
import subprocess

import ssh_host

class ConmuxSSHHost(ssh_host.SSHHost):
	"""This class represents a remote machine controlled through a serial 
	console on which you can run programs. It is not the machine autoserv 
	is running on.
	
	For a machine controlled in this way, it may be possible to support 
	hard reset, boot strap monitoring or other operations not possible 
	on a machine controlled through ssh, telnet, ..."""
	
	def __init__(self,
		     hostname,
		     logfilename=None,
		     server='localhost',
		     attach='/usr/local/conmux/bin/conmux-attach'):
		super(ConmuxSSHHost, self).__init__(hostname)
		self.server = server
		self.attach = attach
		self.pid = None
		self.__start_console_log(logfilename)

	
	def hardreset(self):
		"""
		Reach out and slap the box in the power switch
		"""
		self.__console_run(r"'~$hardreset'")


	def __start_console_log(self, logfilename):
		"""
		Log the output of the console session to a specified file
		"""
		if not os.path.exists(self.attach):
			return
		cmd = [self.attach, '%s/%s' % (self.server, self.hostname), \
						'cat - > %s' % logfilename ]
		self.pid = subprocess.Popen(cmd).pid


	def __console_run(self, cmd):
		"""
		Send a command to the conmux session
		"""
		cmd = '%s %s/%s echo %s' % (self.attach,
					    self.server,
					    self.hostname,
					    cmd)
		os.system(cmd)


	def __del__(self):
		if self.pid:
			os.kill(self.pid, signal.SIGTERM)
		super(ConmuxSSHHost, self).__del__()
		
