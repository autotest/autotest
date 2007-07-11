#!/usr/bin/python
#
# Copyright 2007 Google Inc. Released under the GPL v2

"""This module defines the SiteHost class.

This file may be removed or left empty if no site customization is neccessary.
base_classes.py contains logic to provision for this.

Implementation details:
You should import the "hosts" package instead of importing each type of host.

	SiteHost: Host containing site-specific customizations.
"""

__author__ = """mbligh@google.com (Martin J. Bligh),
poirier@google.com (Benjamin Poirier),
stutsman@google.com (Ryan Stutsman)"""


import base_classes


class SiteHost(base_classes.Host):
	"""Custom host to containing site-specific methods or attributes.
	"""
	
	def __init__(self):
		super(SiteHost, self).__init__()
	
	#def get_platform(self):
		#...
	
	#def get_bios_version(self):
		#...
