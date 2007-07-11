#!/usr/bin/python
#
# Copyright 2007 Google Inc. Released under the GPL v2

"""This module defines the Lilo class.

Implementation details:
You should import the "hosts" package instead of importing this module directly.

	Lilo: a particular Bootloader
"""

__author__ = """mbligh@google.com (Martin J. Bligh),
poirier@google.com (Benjamin Poirier),
stutsman@google.com (Ryan Stutsman)"""


import bootloader


class Lilo(bootloader.Bootloader):
	"""This class represents the Lilo bootloader.
	
	It can be used to add a kernel to the list of kernels that can be 
	booted. It can also make sure that this kernel will be the one 
	chosen at next reboot.
	
	Implementation details:
	This is a leaf class in an abstract class hierarchy, it must 
	implement the unimplemented methods in parent classes.
	"""
	
	pass
