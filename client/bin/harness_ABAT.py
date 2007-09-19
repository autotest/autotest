"""The ABAT harness interface

The interface as required for ABAT.
"""

__author__ = """Copyright Andy Whitcroft 2006"""

from autotest_utils import *
import os, harness, time, re

def autobench_load(fn):
	disks = re.compile(r'^\s*DATS_FREE_DISKS\s*=(.*\S)\s*$')
	parts = re.compile(r'^\s*DATS_FREE_PARTITIONS\s*=(.*\S)\s*$')

	conf = {}

	try:
		fd = file(fn, "r")
	except:
		return conf
	for ln in fd.readlines():
		m = disks.match(ln)
		if m:
			val = m.groups()[0]
			conf['disks'] = val.strip('"').split()
		m = parts.match(ln)
		if m:
			val = m.groups()[0]
			conf['partitions'] = val.strip('"').split()
	fd.close()

	return conf


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
		self.setup(job)

		if 'ABAT_STATUS' in os.environ:
			self.status = file(os.environ['ABAT_STATUS'], "w")
		else:
			self.status = None


	def __send(self, msg):
		if self.status:
			msg = msg.rstrip()
			self.status.write(msg + "\n")
			self.status.flush()


	def __root_device(self):
		fd = open("/proc/mounts", "r")
		try: 
			for line in fd.readlines():
				words = line.split(' ')
				if words[0] != 'rootfs' and words[1] == '/':
					return words[0]
			return None
		finally:
			fd.close()
		

	def run_start(self):
		"""A run within this job is starting"""
		self.__send("STATUS\tGOOD\t----\trun starting")

		# Load up the autobench.conf if it exists.
		conf = autobench_load("/etc/autobench.conf")
		if 'partitions' in conf:
			self.job.config_set('filesystem.partitions',
				conf['partitions'])

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
			args = re.sub(r'root=\S*', '', args)
			args += " root=" + self.__root_device()

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
		self.__send("STATUS\tABORT\t----\trun aborted")
		self.__send("DONE")


	def run_complete(self):
		"""A run within this job is completing (all done)"""
		self.__send("STATUS\tGOOD\t----\trun complete")
		self.__send("DONE")


	def test_status(self, status):
		"""A test within this job is completing"""

		# Send the first line with the status code as a STATUS message.
		lines = status.split("\n")
		self.__send("STATUS\t" + lines[0])

		# Send each line as a SUMMARY message.
		for line in lines:
			self.__send("SUMMARY :" + line)
