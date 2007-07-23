#!/usr/bin/python
#
# Copyright 2007 Google Inc. Released under the GPL v2

"""This module defines the Host class.

Implementation details:
You should import the "hosts" package instead of importing each type of host.

	KVMGuest: a KVM virtual machine on which you can run programs
"""

__author__ = """mbligh@google.com (Martin J. Bligh),
poirier@google.com (Benjamin Poirier),
stutsman@google.com (Ryan Stutsman)"""


import guest


class KVMGuest(guest.Guest):
	"""This class represents a KVM virtual machine on which you can run 
	programs.
	
	Implementation details:
	This is a leaf class in an abstract class hierarchy, it must 
	implement the unimplemented methods in parent classes.
	"""
	
	def __init__(self, controlling_hypervisor, qemu_options):
		"""Construct a KVMGuest object
		
		Args:
			controlling_hypervisor: hypervisor object that is 
				responsible for the creation and management of 
				this guest
			qemu_options: options to pass to qemu, these should be
				appropriately shell escaped, if need be.
		"""
		hostname= controlling_hypervisor.new_guest(qemu_options)
		# bypass Guest's __init__
		super(guest.Guest, self).__init__(hostname)
		self.controlling_hypervisor= controlling_hypervisor
