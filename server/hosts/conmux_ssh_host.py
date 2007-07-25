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
import sys
import signal
import subprocess

import utils
import ssh_host
import errors

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
		     server=None,
		     attach=None, *args, **kwargs):
		super(ConmuxSSHHost, self).__init__(hostname, *args, **kwargs)
		self.server = server
		self.attach = attach
		self.attach = self.__find_console_attach()
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
		if not self.attach or not os.path.exists(self.attach):
			return
		if self.server:
			to = '%s/%s' % (self.server, self.hostname)
		else:
			to = self.hostname
		cmd = [self.attach, to, 'cat - > %s' % logfilename]
		self.pid = subprocess.Popen(cmd).pid

		
	def __find_console_attach(self):
		if self.attach:
			return self.attach
		try:
			res = utils.run('which conmux-attach')
			if res.exit_status == 0:
				return res.stdout.strip()
		except errors.AutoservRunError, e:
			pass
		autoserv_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
		autotest_conmux = os.path.join(autoserv_dir, '..',
					       'conmux', 'conmux-attach')
		autotest_conmux_alt = os.path.join(autoserv_dir,
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
		if not self.attach or not os.path.exists(self.attach):
			return
		if self.server:
			to = '%s/%s' % (self.server, self.hostname)
		else:
			to = self.hostname
		cmd = '%s %s echo %s' % (self.attach,
					 to,
					 cmd)
		os.system(cmd)


	def __del__(self):
		if self.pid:
			os.kill(self.pid, signal.SIGTERM)
		super(ConmuxSSHHost, self).__del__()
		
