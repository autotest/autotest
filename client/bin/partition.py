__author__ = """Copyright Martin J. Bligh, Google, 2006"""

import os, re, string, sys
from autotest_lib.client.bin import autotest_utils
from autotest_lib.client.common_lib import error, utils


class FsOptions(object):
    """A class encapsulating a filesystem test's parameters.

    Properties:  (all strings)
      filesystem: The filesystem type ('ext2', 'ext4', 'xfs', etc.)
      mkfs_flags: Additional command line options to mkfs or '' if none.
      mount_options: The options to pass to mount -o or '' if none.
      short_name: A short name for this filesystem test to use in the results.
    """
    # NOTE(gps): This class could grow or be merged with something else in the
    # future that actually uses the encapsulated data (say to run mkfs) rather
    # than just being a container.
    # Ex: fsdev_disks.mkfs_all_disks really should become a method.

    __slots__ = ('filesystem', 'mkfs_flags', 'mount_options', 'short_name')

    def __init__(self, filesystem, mkfs_flags, mount_options, short_name):
        """Fill in our properties."""
        if not filesystem or not short_name:
            raise ValueError('A filesystem and short_name are required.')
        self.filesystem = filesystem
        self.mkfs_flags = mkfs_flags
        self.mount_options = mount_options
        self.short_name = short_name


    def __str__(self):
        val = ('FsOptions(filesystem=%r, mkfs_flags=%r, '
               'mount_options=%r, short_name=%r)' %
               (self.filesystem, self.mkfs_flags,
                self.mount_options, self.short_name))
        return val


def list_mount_devices():
    devices = []
    # list mounted filesystems
    for line in utils.system_output('mount').splitlines():
        devices.append(line.split()[0])
    # list mounted swap devices
    for line in utils.system_output('swapon -s').splitlines():
        if line.startswith('/'):        # skip header line
            devices.append(line.split()[0])
    return devices


def list_mount_points():
    mountpoints = []
    for line in utils.system_output('mount').splitlines():
        mountpoints.append(line.split()[2])
    return mountpoints


def get_iosched_path(device_name, component):
    return '/sys/block/%s/queue/%s' % (device_name, component)


def wipe_filesystem(job, mountpoint):
    wipe_cmd = 'rm -rf %s/*' % mountpoint
    try:
        utils.system(wipe_cmd)
    except:
        job.record('FAIL', None, wipe_cmd, error.format_error())
        raise
    else:
        job.record('GOOD', None, wipe_cmd)


class partition:
    """
    Class for handling partitions.
    """

    def __init__(self, job, device, mountpoint, loop_size=0):
        """
        device should be able to be a file as well
        which we mount as loopback.

        job
                A client.bin.job instance.
        device
                The device in question (eg "/dev/hda2")
        mountpoint
                Default mountpoint for the device.
        loop_size
                Size of loopback device (in MB).  Defaults to 0.
        """

        part = re.compile(r'^part(\d+)$')
        m = part.match(device)
        if m:
            number = int(m.groups()[0])
            partitions = job.config_get('partition.partitions')
            try:
                device = partitions[number]
            except:
                raise NameError("Partition '" + device + "' not available")

        self.device = device
        self.mountpoint = mountpoint
        self.job = job
        self.fstype = None
        self.loop = loop_size
        if self.loop:
            utils.system('dd if=/dev/zero of=%s bs=1M count=%d' % \
                                            (device, loop_size))


    def mkfs(self, fstype='ext2', args=''):
        """
        Format a partition to fstype
        """
        if list_mount_devices().count(self.device):
            raise NameError('Attempted to format mounted device')
        if fstype == 'xfs':
            args += ' -f'
        if self.loop:
            # BAH. Inconsistent mkfs syntax SUCKS.
            if fstype.startswith('ext'):
                args += ' -F'
            elif fstype == 'reiserfs':
                args += ' -f'
        args = args.lstrip()
        mkfs_cmd = "mkfs -t %s %s %s" % (fstype, args, self.device)
        print mkfs_cmd
        sys.stdout.flush()
        try:
            utils.system("yes | " + mkfs_cmd)
        except:
            self.job.record('FAIL', None, mkfs_cmd, error.format_error())
            raise
        else:
            self.job.record('GOOD', None, mkfs_cmd)
            self.fstype = fstype


    def fsck(self, args='-n'):
        # I hate reiserfstools.
        # Requires an explit Yes for some inane reason
        fsck_cmd = 'fsck %s %s' % (self.device, args)
        if self.fstype == 'reiserfs':
            fsck_cmd = 'yes "Yes" | ' + fsck_cmd
        print fsck_cmd
        sys.stdout.flush()
        try:
            utils.system("yes | " + fsck_cmd)
        except:
            self.job.record('FAIL', None, fsck_cmd, error.format_error())
            raise
        else:
            self.job.record('GOOD', None, fsck_cmd)


    def mount(self, mountpoint=None, fstype=None, args=''):
        if fstype is None:
            fstype = self.fstype
        else:
            assert(self.fstype == None or self.fstype == fstype);
        if fstype:
            args += ' -t ' + fstype
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
            utils.system(mount_cmd)
        except:
            self.job.record('FAIL', None, mount_cmd, error.format_error())
            raise
        else:
            self.job.record('GOOD', None, mount_cmd)
            self.mountpoint = mountpoint
            self.fstype = fstype


    def unmount(self, handle=None):
        if not handle:
            handle = self.device
        umount_cmd = "umount " + handle
        print umount_cmd
        sys.stdout.flush()
        try:
            utils.system(umount_cmd)
        except:
            self.job.record('FAIL', None, umount_cmd, error.format_error())
            raise
        else:
            self.job.record('GOOD', None, umount_cmd)


    def wipe(self):
        wipe_filesystem(self.job, self.mountpoint)


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
