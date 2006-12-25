"""The ABAT harness interface

The interface as required for ABAT.
"""

__author__ = """Copyright Andy Whitcroft 2006"""

from autotest_utils import *
import os, harness, time

class harness_ABAT(harness.harness):
	"""The ABAT server harness

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

		if 'ABAT_STATUS' in os.environ:
			self.status = file(os.environ['ABAT_STATUS'], "w")
		else:
			self.status = None


	def __send(self, msg):
		if self.status:
			msg = msg.rstrip()
			self.status.write(msg + "\n")
			self.status.flush()


	def run_start(self):
		"""A run within this job is starting"""
		self.__send("STATUS GOOD run starting")

		# Search the boot loader configuration for the autobench entry,
		# and extract its args.
		entry_args = None
		args = None
		for line in self.job.bootloader.info('all').split('\n'):
			if line.startswith('args'):
				entry_args = line.split(None, 2)[2]
			if line.startswith('title'):
				title = line.split()[2]
				if title == 'autobench':
					args = entry_args

		if args:
			args = re.sub(r'autobench_args:.*', '', args)
			self.job.config_set('boot.default_args', args)


	def run_reboot(self):
		"""A run within this job is performing a reboot
		   (expect continue following reboot)
		"""
		self.__send("REBOOT")

		# Give lamb-payload some time to get used to the
		# idea we are booting before we let the actual reboot
		# kill it.
		time.sleep(5)


	def run_abort(self):
		"""A run within this job is aborting. It all went wrong"""
		self.__send("STATUS ABORT run aborted")
		self.__send("DONE")


	def run_complete(self):
		"""A run within this job is completing (all done)"""
		self.__send("STATUS GOOD run complete")
		self.__send("DONE")


	def test_status(self, status):
		"""A test within this job is completing"""

		# Send the first line with the status code as a STATUS message.
		lines = status.split("\n")
		self.__send("STATUS " + lines[0])

		# Strip the status code and send the whole thing as
		# SUMMARY messages.
		(status, mesg) = lines[0].split(' ', 1)
		lines[0] = mesg
		for line in lines:
			self.__send("SUMMARY :" + line)
