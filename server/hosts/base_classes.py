#!/usr/bin/python
#
# Copyright 2007 Google Inc. Released under the GPL v2

"""
This module defines the base classes for the Host hierarchy.

Implementation details:
You should import the "hosts" package instead of importing each type of host.

	Host: a machine on which you can run programs
	RemoteHost: a remote machine on which you can run programs
"""

__author__ = """
mbligh@google.com (Martin J. Bligh),
poirier@google.com (Benjamin Poirier),
stutsman@google.com (Ryan Stutsman)
"""

import time
import bootloader, utils

class Host(object):
	"""
	This class represents a machine on which you can run programs.

	It may be a local machine, the one autoserv is running on, a remote 
	machine or a virtual machine.

	Implementation details:
	This is an abstract class, leaf subclasses must implement the methods
	listed here. You must not instantiate this class but should 
	instantiate one of those leaf subclasses.
	"""

	bootloader = None

	def __init__(self):
		super(Host, self).__init__()
		self.serverdir = utils.get_server_dir()
		self.bootloader= bootloader.Bootloader(self)
		self.env = {}


	def run(self, command):
		pass


	def reboot(self):
		pass

	def reboot_setup(self):
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


	def machine_install(self):
		raise "Machine install not implemented!"


	def install(self, installableObject):
		installableObject.install(self)

	def get_crashdumps(self, test_start_time):
		pass


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
