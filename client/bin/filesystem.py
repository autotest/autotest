__author__ = """Copyright Martin J. Bligh, Google, 2006"""

import os, re, string
from autotest_utils import *

def list_mount_devices():
	devices = []
	# list mounted filesystems
	for line in system_output('mount').splitlines():
		devices.append(line.split()[0])
	# list mounted swap devices
	for line in system_output('swapon -s').splitlines():
		if line.startswith('/'):	# skip header line
			devices.append(line.split()[0])
	return devices


def list_mount_points():
	mountpoints = []
	for line in system_output('mount').splitlines():
		mountpoints.append(line.split()[2])
	return mountpoints 


class filesystem:
	"""
	Class for handling filesystems
	"""

	def __init__(self, job, device, mountpoint):
		"""
		device should be able to be a file as well
		which we mount as loopback

		device
			The device in question (eg "/dev/hda2")
		mountpoint
			Default mountpoint for the device.
		"""

		part = re.compile(r'^part(\d+)$')
		m = part.match(device)
		if m:
			number = int(m.groups()[0])
			partitions = job.config_get('filesystem.partitions')
			try:
				device = partitions[number]
			except:
				raise NameError("Partition '" + device +
					"' not available")

		self.device = device
		self.mountpoint = mountpoint
		self.job = job
		self.fstype = None


	def mkfs(self, fstype = 'ext2'):
		"""
		Format a partition to fstype
		"""
		if list_mount_devices().count(self.device):
			raise NameError('Attempted to format mounted device')
		args = ''
		if fstype == 'xfs':
			args = '-f'
		mkfs = "mkfs -t %s %s %s" % (fstype, args, self.device)
		try:
			system("yes | " + mkfs)
		except:
			self.job.record("FAIL " + mkfs)
		else:
			self.job.record("GOOD " + mkfs)
			self.fstype = fstype
			


	def fsck(self, args = ''):
		ret = system('fsck %s %s' % (self.device, args), ignorestatus=1)
		return not ret

	
	def mount(self, mountpoint = None, options = ''):
		if not mountpoint:
			mountpoint = self.mountpoint
		if list_mount_devices().count(self.device):
			err = 'Attempted to mount mounted device'
			self.job.record("FAIL " + err)
			raise NameError(err)
		if list_mount_points().count(mountpoint):
			err = 'Attempted to mount busy mountpoint'
			self.job.record("FAIL " + err)
			raise NameError(err)
		if self.fstype:
			options += ' -t ' + self.fstype
		mount_cmd = "mount %s %s %s" % (options,
						self.device, mountpoint)
		try:
			system(mount_cmd)
		except:
			self.job.record("FAIL " + mount_cmd)
			raise
		else:
			self.job.record("GOOD " + mount_cmd)


	def unmount(self, handle=None):
		if not handle:
			handle = self.device
		system("umount " + handle)
	

	def get_io_scheduler_list(self, device_name):
		names = open(self.__sched_path(device_name)).read()
		return names.translate(string.maketrans('[]', '  ')).split()


	def get_io_scheduler(self, device_name):
		return re.split('[\[\]]',
				open(self.__sched_path(device_name)).read())[1]


	def set_io_scheduler(self, device_name, name):
		if name not in self.get_io_scheduler_list(device_name):
			raise NameError('No such IO scheduler: %s' % name)
		f = open(self.__sched_path(device_name), 'w')
		print >> f, name
		f.close()


	def __sched_path(self, device_name):
		return '/sys/block/%s/queue/scheduler' % device_name
