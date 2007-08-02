#!/usr/bin/python
#
# Copyright 2007 Google Inc. Released under the GPL v2

"""
This module defines the Kernel class

	Kernel: an os kernel
"""

__author__ = """
mbligh@google.com (Martin J. Bligh),
poirier@google.com (Benjamin Poirier),
stutsman@google.com (Ryan Stutsman)"""


import kernel


class RPMKernel(kernel.Kernel):
	"""
	This class represents a .rpm pre-built kernel.
	
	It is used to obtain a built kernel and install it on a Host.
	
	Implementation details:
	This is a leaf class in an abstract class hierarchy, it must 
	implement the unimplemented methods in parent classes.
	"""
	
	pass
