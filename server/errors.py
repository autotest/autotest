#!/usr/bin/python
#
# Copyright 2007 Google Inc. Released under the GPL v2

"""
Exceptions deliberatly thrown by autoserv
"""

__author__ = """
mbligh@google.com (Martin J. Bligh),
poirier@google.com (Benjamin Poirier),
stutsman@google.com (Ryan Stutsman)
"""


class AutoservError(Exception):
	pass


class AutoservRunError(AutoservError):
	"""Errors raised by one of the run functions"""
	pass


class AutoservVirtError(AutoservError):
	"""Vitualization related error"""
	pass

class AutoservHostError(AutoservError):
	"""Error reaching a host"""
	pass
