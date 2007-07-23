#!/usr/bin/python
#
# Copyright 2007 Google Inc. Released under the GPL v2

"""This module defines the base classes for the Host hierarchy.

Implementation details:
You should import the "hosts" package instead of importing each type of host.

	Host: a machine on which you can run programs
	RemoteHost: a remote machine on which you can run programs
	CmdResult: contain the results of a Host.run() command execution
"""

__author__ = """mbligh@google.com (Martin J. Bligh),
poirier@google.com (Benjamin Poirier),
stutsman@google.com (Ryan Stutsman)"""


import time
import textwrap
import bootloader

class Host(object):
	"""This class represents a machine on which you can run programs.
	
	It may be a local machine, the one autoserv is running on, a remote 
	machine or a virtual machine.
	
	Implementation details:
	This is an abstract class, leaf subclasses must implement the methods
	listed here. You must not instantiate this class but should 
	instantiate one of those leaf subclasses."""
	
	bootloader = None
	
	def __init__(self):
		super(Host, self).__init__()
		self.bootloader= bootloader.Bootloader(self)
	
	def run(self, command):
		pass
	
	def reboot(self):
		pass
	
	def get_file(self, source, dest):
		pass
	
	def send_file(self, source, dest):
		pass
	
	def get_tmp_dir(self):
		pass
	
	def is_up(self):
		pass
	
	def wait_up(self, timeout):
		pass
	
	def wait_down(self, timeout):
		pass
	
	def get_num_cpu(self):
		pass
	
	def install(self, installableObject):
		installableObject.install(self)


# site_host.py may be non-existant or empty, make sure that an appropriate 
# SiteHost class is created nevertheless
try:
	from site_host import SiteHost
except ImportError:
	pass

if not "SiteHost" in dir():
	class SiteHost(Host):
		def __init__(self):
			super(SiteHost, self).__init__()


class RemoteHost(SiteHost):
	"""This class represents a remote machine on which you can run 
	programs.
	
	It may be accessed through a network, a serial line, ...
	It is not the machine autoserv is running on.
	
	Implementation details:
	This is an abstract class, leaf subclasses must implement the methods
	listed here and in parent classes which have no implementation. They 
	may reimplement methods which already have an implementation. You 
	must not instantiate this class but should instantiate one of those 
	leaf subclasses."""
	
	hostname= None
	
	def __init__(self):
		super(RemoteHost, self).__init__()


class CmdResult(object):
	"""
	Command execution result.
	
	Modified from the original Autoserv code, local_cmd.py:
		Copyright jonmayer@google.com (Jonathan Mayer),
		mbligh@google.com   (Martin J. Bligh)
		Released under the GPL, v2
	
	command: String containing the command line itself
	exit_status: Integer exit code of the process
	stdout: String containing stdout of the process
	stderr: String containing stderr of the process
	duration: Elapsed wall clock time running the process
	aborted: Signal that caused the command to terminate (0 if none)
	"""
	
	def __init__(self):
		super(CmdResult, self).__init__()
		self.command = ""
		self.exit_status = None
		self.stdout = ""
		self.stderr = ""
		self.duration = 0
		self.aborted= False
	
	def __repr__(self):
		wrapper= textwrap.TextWrapper(width=78, 
			initial_indent="\n    ", subsequent_indent="    ")
		
		stdout= self.stdout.rstrip(" \n")
		if stdout:
			stdout= "\nStdout:\n%s" % (stdout,)
		
		stderr= self.stderr.rstrip(" \n")
		if stderr:
			stderr= "\nStderr:\n%s" % (stderr,)
		
		return ("* Command: %s\n"
			"Exit status: %s\n"
			"Duration: %s\n"
			"Aborted: %s"
			"%s"
			"%s"
			% (wrapper.fill(self.command), self.exit_status, 
			self.duration, self.aborted, stdout, stderr))
