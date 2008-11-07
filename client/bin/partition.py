# Copyright Martin J. Bligh, Google, 2006-2008

import os, re, string, sys, fcntl
from autotest_lib.client.bin import autotest_utils
from autotest_lib.client.common_lib import error, utils


class FsOptions(object):
    """A class encapsulating a filesystem test's parameters.

    Properties:  (all strings)
      fstype: The filesystem type ('ext2', 'ext4', 'xfs', etc.)
      mkfs_flags: Additional command line options to mkfs or '' if none.
      mount_options: The options to pass to mount -o or '' if none.
      fs_tag: A short name for this filesystem test to use in the results.
    """
    # NOTE(gps): This class could grow or be merged with something else in the
    # future that actually uses the encapsulated data (say to run mkfs) rather
    # than just being a container.
    # Ex: fsdev_disks.mkfs_all_disks really should become a method.

    __slots__ = ('fstype', 'mkfs_flags', 'mount_options', 'fs_tag')

    def __init__(self, fstype, mkfs_flags, mount_options, fs_tag):
        """Fill in our properties."""
        if not fstype or not fs_tag:
            raise ValueError('A filesystem and fs_tag are required.')
        self.fstype = fstype 
        self.mkfs_flags = mkfs_flags
        self.mount_options = mount_options
        self.fs_tag = fs_tag


    def __str__(self):
        val = ('FsOptions(fstype=%r, mkfs_flags=%r, '
               'mount_options=%r, fs_tag=%r)' %
               (self.fstype, self.mkfs_flags,
                self.mount_options, self.fs_tag))
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


def get_partition_list(job):
    partitions = []
    for partline in open('/proc/partitions').readlines():
        fields = partline.strip().split()
        if len(fields) != 4 or partline.startswith('major'):
            continue
        (major, minor, blocks, partname) = fields

        # The partition name better end with a digit, else it's not a partition
        if not partname[-1:].isdigit():
            continue

        device = '/dev/' + partname

        partitions.append(partition(job, device))

    return partitions


def parallel(partitions, method_name, *args, **dargs):
    """\
    Run a partition method (with appropriate arguments) in parallel,
    across a list of partition objects
    """
    if not partitions:
        return
    job = partitions[0].job
    flist = []
    if (not hasattr(partition, method_name) or
                               not callable(getattr(partition, method_name))):
        err = "partition.parallel got invalid method %s" % method_name
        raise RuntimeError(err)

    for p in partitions:
        print_args = list(args)
        print_args += ['%s=%s' % (key, dargs[key]) for key in dargs.keys()]
        print '%s.%s(%s)' % (str(p), method_name, ', '.join(print_args))
        sys.stdout.flush()
        def func(function, part=p):
            getattr(part, method_name)(*args, **dargs)
        flist.append((func, ()))
    job.parallel(*flist)


def filesystems():
    """\
    Return a list of all available filesystems
    """
    return [re.sub('(nodev)?\s*', '', fs) for fs in open('/proc/filesystems')]


class partition:
    """
    Class for handling partitions and filesystems
    """

    def __init__(self, job, device, mountpoint=None, loop_size=0):
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
                Size of loopback device (in MB). Defaults to 0.
        """

        self.device = device
        self.name = os.path.basename(device)
        self.job = job
        self.loop = loop_size
        self.fstype = None
        self.mkfs_flags = None
        self.mount_options = None
        self.fs_tag = None
        if self.loop:
            cmd = 'dd if=/dev/zero of=%s bs=1M count=%d' % (device, loop_size)
            utils.system(cmd)
        if mountpoint:
            self.mountpoint = mountpoint
        else:
            self.mountpoint = self.get_mountpoint()


    def __repr__(self):
        return '<Partition: %s>' % self.device


    def set_fs_options(self, fs_options):
        self.fstype = fs_options.fstype
        self.mkfs_flags = fs_options.mkfs_flags
        self.mount_options = fs_options.mount_options
        self.fs_tag = fs_options.fs_tag


    def run_test(self, test, **dargs):
        self.job.run_test(test, tag=tag, dir=self.mountpoint, **dargs)


    def run_test_on_partition(self, test, **dargs):
        tag = dargs.pop('tag', None)
        if tag:
            tag = '%s.%s' % (self.name, tag)
        else:
            if self.fs_tag:
                tag = '%s.%s' % (self.name, self.fs_tag)
            else:
                tag = self.name

        def func(test_tag, dir, **dargs):
            self.unmount(ignore_status=True, record=False)
            self.mkfs()
            self.mount()
            try:
                self.job.run_test(test, tag=test_tag, dir=dir, **dargs)
            finally:
                self.unmount()
                self.fsck()

        # The tag is the tag for the group (get stripped off by run_group)
        # The test_tag is the tag for the test itself
        self.job.run_group(func, test_tag=tag, tag=test + '.' + tag,
                           dir=self.mountpoint, **dargs)


    def get_mountpoint(self):
        for line in open('/etc/mtab', 'r').readlines():
            parts = line.split()
            if parts[0] == self.device:
                return parts[1]          # The mountpoint where it's mounted
        return None


    def mkfs(self, fstype=None, args='', record=True):
        """
        Format a partition to fstype
        """
        if list_mount_devices().count(self.device):
            raise NameError('Attempted to format mounted device')

        if not fstype:
            if self.fstype:
                fstype = self.fstype
            else:
                fstype = 'ext2'

        if self.mkfs_flags:
            args += ' ' + self.mkfs_flags
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
            # We throw away the output here - we only need it on error, in
            # which case it's in the exception
            utils.system_output("yes | %s" % mkfs_cmd)
        except error.CmdError, e:
            print e.result_obj
            if record:
                self.job.record('FAIL', None, mkfs_cmd, error.format_error())
            raise
        except:
            if record:
                self.job.record('FAIL', None, mkfs_cmd, error.format_error())
            raise
        else:
            if record:
                self.job.record('GOOD', None, mkfs_cmd)
            self.fstype = fstype


    def fsck(self, args='-n', record=True):
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
            if record:
                self.job.record('FAIL', None, fsck_cmd, error.format_error())
            raise
        else:
            if record:
                self.job.record('GOOD', None, fsck_cmd)


    def mount(self, mountpoint=None, fstype=None, args='', record=True):
        if fstype is None:
            fstype = self.fstype
        else:
            assert(self.fstype == None or self.fstype == fstype);

        if self.mount_options:
            args += ' ' + self.mount_options
        if fstype:
            args += ' -t ' + fstype
        if self.loop:
            args += ' -o loop'
        args = args.lstrip()

        if not mountpoint:
            mountpoint = self.mountpoint

        mount_cmd = "mount %s %s %s" % (args, self.device, mountpoint)
        print mount_cmd

        if list_mount_devices().count(self.device):
            err = 'Attempted to mount mounted device'
            self.job.record('FAIL', None, mount_cmd, err)
            raise NameError(err)
        if list_mount_points().count(mountpoint):
            err = 'Attempted to mount busy mountpoint'
            self.job.record('FAIL', None, mount_cmd, err)
            raise NameError(err)

        mtab = open('/etc/mtab')
        # We have to get an exclusive lock here - mount/umount are racy
        fcntl.flock(mtab.fileno(), fcntl.LOCK_EX)
        print mount_cmd
        sys.stdout.flush()
        try:
            utils.system(mount_cmd)
            mtab.close()
        except:
            mtab.close()
            if record:
                self.job.record('FAIL', None, mount_cmd, error.format_error())
            raise
        else:
            if record:
                self.job.record('GOOD', None, mount_cmd)
            self.mountpoint = mountpoint
            self.fstype = fstype


    def unmount(self, handle=None, ignore_status=False, record=True):
        if not handle:
            handle = self.device
        mtab = open('/etc/mtab')
        # We have to get an exclusive lock here - mount/umount are racy
        fcntl.flock(mtab.fileno(), fcntl.LOCK_EX)
        umount_cmd = "umount " + handle
        print umount_cmd
        sys.stdout.flush()
        try:
            utils.system(umount_cmd, ignore_status=ignore_status)
            mtab.close()
        except:
            mtab.close()
            if record:
                self.job.record('FAIL', None, umount_cmd, error.format_error())
            raise
        else:
            if record:
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
