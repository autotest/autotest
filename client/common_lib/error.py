"""
Internal global error types
"""

import sys
from traceback import format_exception

def format_error():
        t, o, tb = sys.exc_info()
        trace = format_exception(t, o, tb)
        # Clear the backtrace to prevent a circular reference
        # in the heap -- as per tutorial
        tb = ''

        return ''.join(trace)

class JobContinue(SystemExit):
	"""Allow us to bail out requesting continuance."""
	pass

class JobComplete(SystemExit):
	"""Allow us to bail out indicating continuation not required."""
	pass

class AutotestError(Exception):
	"""The parent of all errors deliberatly thrown within the client code."""
	pass

class JobError(AutotestError):
	"""Indicates an error which terminates and fails the whole job."""
	pass

class TestError(AutotestError):
	"""Indicates an error which terminates and fails the test."""
	pass

class CmdError(TestError):
	"""Indicates that a command failed, is fatal to the test unless caught."""
	def __str__(self):
		return "Command <" + self.args[0] + "> failed, rc=%d" % (self.args[1])

class PackageError(TestError):
       """Indicates an error trying to perform a package operation."""

class UnhandledError(TestError):
	"""Indicates an unhandled exception in a test."""
	def __init__(self, prefix):
		msg = prefix + format_error()
		TestError.__init__(self, msg)

class InstallError(JobError):
	"""Indicates an installation error which Terminates and fails the job."""
	pass

# server-specific errors

class AutoservError(Exception):
	pass


class AutoservRunError(AutoservError):
	"""Errors raised by one of the run functions"""
	pass


class AutoservVirtError(AutoservError):
	"""Vitualization related error"""
	pass


class AutoservUnsupportedError(AutoservError):
	"""Error raised when you try to use an unsupported optional feature"""
	pass

class AutoservHostError(AutoservError):
	"""Error reaching a host"""
	pass

class AutoservRebootError(AutoservError):
	"""Error occured while rebooting a machine"""
	pass
