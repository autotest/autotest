__author__ = """Copyright Martin J. Bligh, Google, 2006"""

import os, re, string
from autotest_utils import *
from error import *

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

	def __init__(self, job, device, mountpoint, loop_size = 0):
		"""
		device should be able to be a file as well
		which we mount as loopback

		device
			The device in question (eg "/dev/hda2")
		mountpoint
			Default mountpoint for the device.
		loop_size
			size of loopback device (in MB)
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
		self.loop = loop_size
		if self.loop:
			system('dd if=/dev/zero of=%s bs=1M count=%d' % \
							(device, loop_size))


	def mkfs(self, fstype = 'ext2', args = ''):
		"""
		Format a partition to fstype
		"""
		if list_mount_devices().count(self.device):
			raise NameError('Attempted to format mounted device')
		if fstype == 'xfs':
			args += ' -f'
		if self.loop:
			# BAH. Inconsistent mkfs syntax SUCKS.
			if fstype == 'ext2' or fstype == 'ext3':
				args += ' -F'
			if fstype == 'reiserfs':
				args += ' -f'
		args = args.lstrip()
		mkfs_cmd = "mkfs -t %s %s %s" % (fstype, args, self.device)
		print mkfs_cmd
		sys.stdout.flush()
		try:
			system("yes | " + mkfs_cmd)
		except:
			self.job.record('FAIL', None, mkfs_cmd, format_error())
			raise
		else:
			self.job.record('GOOD', None, mkfs_cmd)
			self.fstype = fstype


	def fsck(self, args = '-n'):
		# I hate reiserfstools.
		# Requires an explit Yes for some inane reason
		fsck = 'fsck %s %s' % (self.device, args)
		if self.fstype == 'reiserfs':
			fsck = 'yes "Yes" | ' + fsck
		print fsck
		sys.stdout.flush()
		system(fsck)

	
	def mount(self, mountpoint = None, args = ''):
		if self.fstype:
			args += ' -t ' + self.fstype
		if self.loop:
			args += ' -o loop'
		args = args.lstrip()

		if not mountpoint:
			mountpoint = self.mountpoint
		mount_cmd = "mount %s %s %s" % (args, self.device, mountpoint)

		if list_mount_devices().count(self.device):
			err = 'Attempted to mount mounted device'
			self.job.record('FAIL', None, mount_cmd, err)
			raise NameError(err)
		if list_mount_points().count(mountpoint):
			err = 'Attempted to mount busy mountpoint'
			self.job.record('FAIL', None, mount_cmd, err)
			raise NameError(err)

		print mount_cmd
		sys.stdout.flush()
		try:
			system(mount_cmd)
		except:
			self.job.record('FAIL', None, mount_cmd, format_error())
			raise
		else:
			self.job.record('GOOD', None, mount_cmd)


	def unmount(self, handle=None):
		if not handle:
			handle = self.device
		umount_cmd = "umount " + handle
		print umount_cmd
		sys.stdout.flush()
		try:
			system(umount_cmd)
		except:
			self.job.record('FAIL', None, umount_cmd, format_error())
			raise
		else:
			self.job.record('GOOD', None, umount_cmd)


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
