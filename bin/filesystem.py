__author__ = """Copyright Martin J. Bligh, Google, 2006"""

import os
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

	def __init__(self, device, mountpoint):
		"""
		device should be able to be a file as well
		which we mount as loopback

		device
			The device in question (eg "/dev/hda2")
		mountpoint
			Default mountpoint for the device.
		"""
		self.device = device
		self.mountpoint = mountpoint


	def mkfs(self, fstype = 'ext2'):
		"""
		Format a partition to fstype
		"""
		if list_mount_devices().count(self.device):
			raise NameError('Attempted to format mounted device')
		system("yes | mkfs -t %s %s" % (fstype, self.device))


	def fsck(self, args = ''):
		ret = system('fsck %s %s' % (self.device, args), ignorestatus=1)
		return not ret

	
	def mount(self, mountpoint=None):
		if not mountpoint:
			mountpoint = self.mountpoint
		if list_mount_devices().count(self.device):
			raise NameError('Attempted to mount mounted device')
		if list_mount_points().count(mountpoint):
			raise NameError('Attempted to mount busy mountpoint')
		system("mount %s %s" % (self.device, mountpoint))


	def unmount(self, handle=None):
		if not handle:
			handle = self.device
		system("umount " + handle)
