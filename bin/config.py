"""The Job Configuration

The job configuration, holding configuration variable supplied to the job.
"""

__author__ = """Copyright Andy Whitcroft 2006"""

import os

class config:
	"""The BASIC job configuration

	Properties:
		job
			The job object for this job
		config
			The job configuration dictionary
	"""

	def __init__(self, job):
		"""
			job
				The job object for this job
		"""
		self.job = job
		self.config = {}


        def set(self, name, value):
		if name == "proxy":
			os.environ['http_proxy'] = value
			os.environ['ftp_proxy'] = value

		self.config[name] = value

	def get(self, name):
		if name in self.config:
			return self.config[name]
		else:
			return None
