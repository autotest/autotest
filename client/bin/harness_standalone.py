"""The standalone harness interface

The default interface as required for the standalone reboot helper.
"""

__author__ = """Copyright Andy Whitcroft 2007"""

from autotest_utils import *
import os, harness, shutil

class harness_standalone(harness.harness):
	"""The standalone server harness

	Properties:
		job
			The job object for this job
	"""

	def __init__(self, job):
		"""
			job
				The job object for this job
		"""

		self.setup(job)

		src = job.control_get()
		dest = os.path.join(os.environ['AUTODIR'], 'control')
		if os.path.abspath(src) != os.path.abspath(dest):
			shutil.copyfile(src, dest)
