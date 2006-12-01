"""The harness interface

The interface between the client and the server when hosted.
"""

__author__ = """Copyright Andy Whitcroft 2006"""

from autotest_utils import *
import os, sys

class harness:
	"""The NULL server harness

	Properties:
		job
			The job object for this job
	"""

	def __init__(self, job):
		"""
			job
				The job object for this job
		"""
		self.job = job


	def run_start(self):
		"""A run within this job is starting"""
		pass


	def run_pause(self):
		"""A run within this job is completing (expect continue)"""
		pass


	def run_reboot(self):
		"""A run within this job is performing a reboot
		   (expect continue following reboot)
		"""
		pass


	def run_complete(self, status):
		"""A run within this job is completing (all done)"""
		pass


	def test_status(self, status):
		"""A test within this job is completing"""
		pass


def select(which, job):
	if which:
		exec "import harness_%s" % (which)
		exec "myharness = harness_%s.harness_%s(job)" % (which, which)
	else:
		myharness = harness(job)

	return myharness
