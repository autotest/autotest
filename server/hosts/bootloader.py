#!/usr/bin/python
#
# Copyright 2007 Google Inc. Released under the GPL v2

"""This module defines the Bootloader class.

	Bootloader: a program to boot Kernels on a Host.
"""

__author__ = """mbligh@google.com (Martin J. Bligh),
poirier@google.com (Benjamin Poirier),
stutsman@google.com (Ryan Stutsman)"""


class Bootloader(object):
	"""This class represents a bootloader.
	
	It can be used to add a kernel to the list of kernels that can be 
	booted by a bootloader. It can also make sure that this kernel will 
	be the one chosen at next reboot.
	
	Implementation details:
	This is an abstract class, leaf subclasses must implement the methods
	listed here. You must not instantiate this class but should 
	instantiate one of those leaf subclasses."""
	
	host = None
	
	def add_entry(self, name, image, initrd, root, options, default=True):
		pass
	
	def remove_entry(self, name):
		pass
