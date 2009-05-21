# Copyright Martin J. Bligh, Google, 2006-2008

import os, re, string, sys, fcntl
import utils
from autotest_lib.client.bin import os_dep
from autotest_lib.client.common_lib import error


class FsOptions(object):
    """
    A class encapsulating a filesystem test's parameters.
    """
    # NOTE(gps): This class could grow or be merged with something else in the
    # future that actually uses the encapsulated data (say to run mkfs) rather
    # than just being a container.
    # Ex: fsdev_disks.mkfs_all_disks really should become a method.

    __slots__ = ('fstype', 'mkfs_flags', 'mount_options', 'fs_tag')

    def __init__(self, fstype, fs_tag, mkfs_flags=None, mount_options=None):
        """
        Fill in our properties.

            @param fstype: The filesystem type ('ext2', 'ext4', 'xfs', etc.)
            @param fs_tag: A short name for this filesystem test to use
                           in the results.
            @param mkfs_flags: Optional. Additional command line options to mkfs.
            @param mount_options: Optional. The options to pass to mount -o.
        """

        if not fstype or not fs_tag:
            raise ValueError('A filesystem and fs_tag are required.')
        self.fstype = fstype
        self.fs_tag = fs_tag
        self.mkfs_flags = mkfs_flags or ""
        self.mount_options = mount_options or ""


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


def is_linux_fs_type(device):
    """
    Checks if specified partition is type 83

        @param device: the device, e.g. /dev/sda3

        @return: False if the supplied partition name is not type 83 linux, True
                otherwise
    """
    disk_device = device.rstrip('0123456789')

    # Parse fdisk output to get partition info.  Ugly but it works.
    fdisk_fd = os.popen("/sbin/fdisk -l -u '%s'" % disk_device)
    fdisk_lines = fdisk_fd.readlines()
    fdisk_fd.close()
    for line in fdisk_lines:
        if not line.startswith(device):
            continue
        info_tuple = line.split()
        # The Id will be in one of two fields depending on if the boot flag
        # was set.  Caveat: this assumes no boot partition will be 83 blocks.
        for fsinfo in info_tuple[4:6]:
            if fsinfo == '83':  # hex 83 is the linux fs partition type
                return True
    return False


@utils.deprecated
def filter_non_linux(part_name):
    """
        @param part_name: e.g. sda2, sda3
        @deprecated: use is_linux_fs_type instead
    """
    device = '/dev/' + part_name
    return is_linux_fs_type(device=device)


def get_partition_list(job, min_blocks=0, filter_func=None, exclude_swap=True,
                       open_func=open):
    """
    Get a list of partition objects for all disk partitions on the system.

    Loopback devices and unnumbered (whole disk) devices are always excluded.

        @param job: The job instance to pass to the partition object
                    constructor.
        @param min_blocks: The minimum number of blocks for a partition to
                           be considered.
        @param filter_func: A callable that returns True if a partition is
                            desired. It will be passed one parameter:
                            The partition name (hdc3, etc.).
                            Some useful filter functions are already defined
                            in this module.
        @param exclude_swap: If True any partition actively in use as a swap
                             device will be excluded.
        @param __open: Reserved for unit testing.

        @return: A list of L{partition} objects.
    """
    active_swap_devices = set()
    if exclude_swap:
        for swapline in open_func('/proc/swaps'):
            if swapline.startswith('/'):
                active_swap_devices.add(swapline.split()[0])

    partitions = []
    for partline in open_func('/proc/partitions').readlines():
        fields = partline.strip().split()
        if len(fields) != 4 or partline.startswith('major'):
            continue
        (major, minor, blocks, partname) = fields
        blocks = int(blocks)

        # The partition name better end with a digit, else it's not a partition
        if not partname[-1].isdigit():
            continue

        # We don't want the loopback device in the partition list
        if 'loop' in partname:
            continue

        device = '/dev/' + partname
        if exclude_swap and device in active_swap_devices:
            print 'get_partition_list() skipping', partname, '- Active swap.'
            continue

        if min_blocks and blocks < min_blocks:
            print 'get_partition_list() skipping', partname, '- Too small.'
            continue

        if filter_func and not filter_func(partname):
            print 'get_partition_list() skipping', partname, '- filter_func.'
            continue

        partitions.append(partition(job, device))

    return partitions


def filter_partition_list(partitions, devnames):
    """
    Pick and choose which partition to keep.

    filter_partition_list accepts a list of partition objects and a list
    of strings.  If a partition has the device name of the strings it
    is returned in a list.

    @param partitions: A list of L{partition} objects
    @param devnames: A list of devnames of the form '/dev/hdc3' that
                    specifies which partitions to include in the returned list.

    @return: A list of L{partition} objects specified by devnames, in the
             order devnames specified
    """

    filtered_list = []
    for p in partitions:
       for d in devnames:
           if p.device == d and p not in filtered_list:
              filtered_list.append(p)

    return filtered_list


def get_unmounted_partition_list(root_part, job=None, min_blocks=0,
                                 filter_func=None, exclude_swap=True,
                                 open_func=open):
    """
    Return a list of partition objects that are not mounted.

    @param root_part the root device name (without the '/dev/' prefix, example
        'hda2') that will be filtered from the partition list

        Reasoning: in Linux /proc/mounts will never directly mention the root
        partition as being mounted on / instead it will say that /dev/root is
        mounted on /. Thus require this argument to filter out the root_part
        from the ones checked to be mounted

    @param job, min_blocks, filter_func, exclude_swap, open_func are forwarded
        to get_partition_list()

    @return a list of L{partition} objects that are not mounted
    """
    partitions = get_partition_list(job=job, min_blocks=min_blocks,
        filter_func=filter_func, exclude_swap=exclude_swap, open_func=open_func)

    unmounted = []
    for part in partitions:
        if (part.device != '/dev/' + root_part and
            not part.get_mountpoint(open_func=open_func)):
            unmounted.append(part)

    return unmounted


def parallel(partitions, method_name, *args, **dargs):
    """
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
        def _run_named_method(function, part=p):
            getattr(part, method_name)(*args, **dargs)
        flist.append((_run_named_method, ()))
    job.parallel(*flist)


def filesystems():
    """
    Return a list of all available filesystems
    """
    return [re.sub('(nodev)?\s*', '', fs) for fs in open('/proc/filesystems')]


def unmount_partition(device):
    """
    Unmount a mounted partition

        @param device: e.g. /dev/sda1, /dev/hda1
    """
    p = partition(job=None, device=device)
    p.unmount(record=False)


def is_valid_partition(device):
    """
    Checks if a partition is valid

        @param device: e.g. /dev/sda1, /dev/hda1
    """
    parts = get_partition_list(job=None)
    p_list = [ p.device for p in parts ]
    if device in p_list:
        return True

    return False


def is_valid_disk(device):
    """
    Checks if a disk is valid

        @param device: e.g. /dev/sda, /dev/hda
    """
    partitions = []
    for partline in open('/proc/partitions').readlines():
        fields = partline.strip().split()
        if len(fields) != 4 or partline.startswith('major'):
            continue
        (major, minor, blocks, partname) = fields
        blocks = int(blocks)

        if not partname[-1].isdigit():
            # Disk name does not end in number, AFAIK
            # so use it as a reference to a disk
            if device.strip("/dev/") == partname:
                return True

    return False


def run_test_on_partitions(job, test, partitions, mountpoint_func,
                           tag, fs_opt, **dargs):
    """\
    Run a test that requires multiple partitions.  Filesystems will be
    made on the partitions and mounted, then the test will run, then the
    filesystems will be unmounted and fsck'd.

    Args:
      job: A job instance to run the test
      test: A string containing the name of the test
      partitions: A list of partition objects, these are passed to the test as
          partitions=
      mountpoint_func: A callable that returns a mountpoint given a partition
          instance
      tag: A string tag to make this test unique (Required for control files
          that make multiple calls to this routine with the same value of
          'test'.)
      fs_opt: An FsOptions instance that describes what filesystem to make
      dargs: Arguments to be passed to job.run_test() and eventually the test
    """
    # setup the filesystem parameters for all the partitions
    for p in partitions:
        p.set_fs_options(fs_opt)

    # make and mount all the partitions in parallel
    parallel(partitions, 'setup_before_test', mountpoint_func=mountpoint_func)

    # run the test against all the partitions
    job.run_test(test, tag=tag, partitions=partitions, **dargs)

    # fsck and then remake all the filesystems in parallel
    parallel(partitions, 'cleanup_after_test')


class partition(object):
    """
    Class for handling partitions and filesystems
    """

    def __init__(self, job, device, loop_size=0, mountpoint=None):
        """
            @param job: A L{client.bin.job} instance.
            @param device: The device in question (e.g."/dev/hda2"). If device
                           is a file it will be mounted as loopback. If you have
                           job config 'partition.partitions', e.g.,
                           job.config_set('partition.partitions', ["/dev/sda2",
                           "/dev/sda3"]) you may specify a partition in the
                           form of "partN" e.g. "part0", "part1" to refer to
                           elements of the partition list.
                           This is specially useful if you run a test in various
                           machines and you don't want to hardcode device
                           names as those may vary.
            @param loop_size: Size of loopback device (in MB). Defaults to 0.
        """
        # NOTE: This code is used by IBM / ABAT. Do not remove.
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
        self.name = os.path.basename(device)
        self.job = job
        self.loop = loop_size
        self.fstype = None
        self.mountpoint = mountpoint
        self.mkfs_flags = None
        self.mount_options = None
        self.fs_tag = None
        if self.loop:
            cmd = 'dd if=/dev/zero of=%s bs=1M count=%d' % (device, loop_size)
            utils.system(cmd)


    def __repr__(self):
        return '<Partition: %s>' % self.device


    def set_fs_options(self, fs_options):
        """
        Set filesystem options

            @param fs_options: A L{FsOptions} object
        """

        self.fstype = fs_options.fstype
        self.mkfs_flags = fs_options.mkfs_flags
        self.mount_options = fs_options.mount_options
        self.fs_tag = fs_options.fs_tag


    def run_test(self, test, **dargs):
        self.job.run_test(test, dir=self.get_mountpoint(), **dargs)


    def setup_before_test(self, mountpoint_func):
        """\
        Prepare a partition for running a test.  Unmounts any
        filesystem that's currently mounted on the partition, makes a
        new filesystem (according to this partition's filesystem
        options) and mounts it where directed by mountpoint_func.

        Args:
          mountpoint_func: A callable that returns a path as a string, given a
          partition instance.
        """
        mountpoint = mountpoint_func(self)
        if not mountpoint:
            raise ValueError('Don\'t know where to put this partition')
        self.unmount(ignore_status=True, record=False)
        self.mkfs()
        self.mount(mountpoint)


    def cleanup_after_test(self):
        """\
        Cleans up a partition after running a filesystem test.  The
        filesystem is unmounted, and then checked for errors.
        """
        self.unmount()
        self.fsck()


    def run_test_on_partition(self, test, mountpoint_func, **dargs):
        """
        Executes a test fs-style (umount,mkfs,mount,test)

        Here we unmarshal the args to set up tags before running the test.
        Tests are also run by first umounting, mkfsing and then mounting
        before executing the test.

            @param test: name of test to run
            @param mountpoint_func: function to return mount point string
        """
        tag = dargs.get('tag')
        if tag:
            tag = '%s.%s' % (self.name, tag)
        elif self.fs_tag:
            tag = '%s.%s' % (self.name, self.fs_tag)
        else:
            tag = self.name

        dargs['tag'] = test + '.' + tag

        def _make_partition_and_run_test(test_tag, dir=None, **dargs):
            self.setup_before_test(mountpoint_func)
            try:
                self.job.run_test(test, tag=test_tag, dir=mountpoint, **dargs)
            finally:
                self.cleanup_after_test()

        mountpoint = mountpoint_func(self)

        # The tag is the tag for the group (get stripped off by run_group)
        # The test_tag is the tag for the test itself
        self.job.run_group(_make_partition_and_run_test,
                           test_tag=tag, dir=mountpoint, **dargs)


    def get_mountpoint(self, open_func=open):
        for line in open_func('/proc/mounts').readlines():
            parts = line.split()
            if parts[0] == self.device:
                return parts[1]          # The mountpoint where it's mounted
        return None


    def mkfs_exec(self, fstype):
        """
        Return the proper mkfs executable based on fs
        """
        if fstype == 'ext4':
            if os.path.exists('/sbin/mkfs.ext4'):
                return 'mkfs'
            # If ext4 supported e2fsprogs is not installed we use the
            # autotest supplied one in tools dir which is statically linked"""
            auto_mkfs = os.path.join(self.job.toolsdir, 'mkfs.ext4dev')
            if os.path.exists(auto_mkfs):
                return auto_mkfs
        else:
            return 'mkfs'

        raise NameError('Error creating partition for filesystem type %s' %
                        fstype)


    def mkfs(self, fstype=None, args='', record=True):
        """
        Format a partition to filesystem type

            @param fstype: the filesystem type, e.g.. "ext3", "ext2"
            @param args: arguments to be passed to mkfs command.
            @param record: if set, output result of mkfs operation to autotest output
        """

        if list_mount_devices().count(self.device):
            raise NameError('Attempted to format mounted device %s' %
                             self.device)

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
        args = args.strip()

        mkfs_cmd = "%s %s %s" % (self.mkfs_exec(fstype), args, self.device)

        # If there isn't already a '-t <type>' argument, add one.
        if not "-t" in args:
            mkfs_cmd += " -t %s" % (fstype)
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


    def get_fsck_exec(self):
        """
        Return the proper mkfs executable based on self.fstype
        """
        if self.fstype == 'ext4':
            if os.path.exists('/sbin/fsck.ext4'):
                return 'fsck'
            # If ext4 supported e2fsprogs is not installed we use the
            # autotest supplied one in tools dir which is statically linked"""
            auto_fsck = os.path.join(self.job.toolsdir, 'fsck.ext4dev')
            if os.path.exists(auto_fsck):
                return auto_fsck
        else:
            return 'fsck'

        raise NameError('Error creating partition for filesystem type %s' %
                        self.fstype)


    def fsck(self, args='-n', record=True):
        """
        Run filesystem check

            @param args: arguments to filesystem check tool. Default is "-n"
                         which works on most tools.
        """


        # I hate reiserfstools.
        # Requires an explit Yes for some inane reason
        fsck_cmd = '%s %s %s' % (self.get_fsck_exec(), self.device, args)
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


    def mount(self, mountpoint, fstype=None, args='', record=True):
        """
        Mount this partition to a mount point

            @param mountpoint: If you have not provided a mountpoint to partition
                            object or want to use a different one, you may speficy
                            it here.
            @param fstype: Filesystem type. If not provided partition object
                           value will be used.
            @param args: Arguments to be passed to "mount" command.
            @param record: If True, output result of mount operation to autotest
                           output.
        """

        if fstype is None:
            fstype = self.fstype
        else:
            assert(self.fstype is None or self.fstype == fstype);

        if self.mount_options:
            args += ' -o  ' + self.mount_options
        if fstype:
            args += ' -t ' + fstype
        if self.loop:
            args += ' -o loop'
        args = args.lstrip()

        if not mountpoint and not self.mountpoint:
            raise ValueError("No mountpoint specified and no default "
                             "provided to this partition object")
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
            self.fstype = fstype


    def unmount_force(self):
       """
       Kill all other jobs accessing this partition

       Use fuser and ps to find all mounts on this mountpoint and unmount them.

           @return: true for success or false for any errors
       """

       print "Standard umount failed, will try forcing. Users:"
       try:
           cmd = 'fuser ' + self.get_mountpoint()
           print cmd
           fuser = utils.system_output(cmd)
           print fuser
           users = re.sub('.*:', '', fuser).split()
           for user in users:
               m = re.match('(\d+)(.*)', user)
               (pid, usage) = (m.group(1), m.group(2))
               try:
                  ps = utils.system_output('ps -p %s | tail +2' % pid)
                  print '%s %s %s' % (usage, pid, ps)
               except Exception:
                  pass
               utils.system('ls -l ' + self.device)
               umount_cmd = "umount -f " + self.device
               print umount_cmd
               utils.system(umount_cmd)
               return True
       except error.CmdError:
           print 'umount_force failed for %s' % self.device
           return False



    def unmount(self, ignore_status=False, record=True):
        """
        Umount this partition.

        It's easier said than done to umount a partition.
        We need to lock the mtab file to make sure we don't have any
        locking problems if we are umounting in paralllel.

        If there turns out to be a problem with the simple umount we
        end up calling umount_force to get more  agressive.

            @param ignore_status: should we notice the umount status
            @param record: if True, output result of umount operation to
                           autotest output
        """

        mountpoint = self.get_mountpoint()
        if not mountpoint:
            # It's not even mounted to start with
            if record and not ignore_status:
                msg = 'umount for dev %s has no mountpoint' % self.device
                self.job.record('FAIL', None, msg, 'Not mounted')
            return

        umount_cmd = "umount " + mountpoint
        mtab = open('/etc/mtab')

        # We have to get an exclusive lock here - mount/umount are racy
        fcntl.flock(mtab.fileno(), fcntl.LOCK_EX)
        print umount_cmd
        sys.stdout.flush()
        try:
            utils.system(umount_cmd)
            mtab.close()
            if record:
                self.job.record('GOOD', None, umount_cmd)
        except (error.CmdError, IOError):
            mtab.close()

            # Try the forceful umount
            if self.unmount_force():
                return

            # If we are here we cannot umount this partition
            if record and not ignore_status:
               self.job.record('FAIL', None, umount_cmd, error.format_error())
            raise


    def wipe(self):
        """ Delete all files of partition filesystem """
        wipe_filesystem(self.job, self.get_mountpoint())


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


class virtual_partition:
    """
    Handles block device emulation using file images of disks.
    It's important to note that this API can be used only if
    we have the following programs present on the client machine:

     * sfdisk
     * losetup
     * kpartx
    """
    def __init__(self, file_img, file_size):
        """
        Creates a virtual partition, keeping record of the device created
        under /dev/mapper (device attribute) so test writers can use it
        on their filesystem tests.

            @param file_img: Path to the desired disk image file.
            @param file_size: Size of the desired image in Bytes.
        """
        print 'Sanity check before attempting to create virtual partition'
        try:
            os_dep.commands('sfdisk', 'losetup', 'kpartx')
        except ValueError, e:
            e_msg = 'Unable to create virtual partition: %s' % e
            raise error.AutotestError(e_msg)

        print 'Creating virtual partition'
        self.img = self.__create_disk_img(file_img, file_size)
        self.loop = self.__attach_img_loop(self.img)
        self.__create_single_partition(self.loop)
        self.device = self.__create_entries_partition(self.loop)
        print 'Virtual partition successfuly created'
        print 'Image disk: %s' % self.img
        print 'Loopback device: %s' % self.loop
        print 'Device path: %s' % self.device


    def destroy(self):
        """
        Removes the virtual partition from /dev/mapper, detaches the image file
        from the loopback device and removes the image file.
        """
        print 'Removing virtual partition - device %s' % self.device
        self.__remove_entries_partition()
        self.__detach_img_loop()
        self.__remove_disk_img()


    def __create_disk_img(self, img_path, size):
        """
        Creates a disk image using dd.

            @param img_path: Path to the desired image file.
            @param size: Size of the desired image in Bytes.
            @returns: Path of the image created.
        """
        print 'Creating disk image %s, size = %s Bytes' % (img_path, size)
        try:
            cmd = 'dd if=/dev/zero of=%s bs=1024 count=%s' % (img_path, size)
            utils.system(cmd)
        except error.CmdError, e:
            e_msg = 'Error creating disk image %s: %s' % (img_path, e)
            raise error.AutotestError(e_msg)
        return img_path


    def __attach_img_loop(self, img_path):
        """
        Attaches a file image to a loopback device using losetup.

            @param img_path: Path of the image file that will be attached to a
            loopback device
            @returns: Path of the loopback device associated.
        """
        print 'Attaching image %s to a loop device' % img_path
        try:
            cmd = 'losetup -f'
            loop_path = utils.system_output(cmd)
            cmd = 'losetup -f %s' % img_path
            utils.system(cmd)
        except error.CmdError, e:
            e_msg = 'Error attaching image %s to a loop device: %s' % \
                     (img_path, e)
            raise error.AutotestError(e_msg)
        return loop_path


    def __create_single_partition(self, loop_path):
        """
        Creates a single partition encompassing the whole 'disk' using cfdisk.

            @param loop_path: Path to the loopback device
        """
        print 'Creating single partition on %s' % loop_path
        try:
            single_part_cmd = '0,,c\n'
            sfdisk_file_path = '/tmp/create_partition.sfdisk'
            sfdisk_cmd_file = open(sfdisk_file_path, 'w')
            sfdisk_cmd_file.write(single_part_cmd)
            sfdisk_cmd_file.close()
            utils.system('sfdisk %s < %s' % (loop_path, sfdisk_file_path))
        except error.CmdError, e:
            e_msg = 'Error partitioning device %s: %s' % (loop_path, e)
            raise error.AutotestError(e_msg)


    def __create_entries_partition(self, loop_path):
        """
        Takes the newly created partition table on the loopback device and
        makes all its devices available under /dev/mapper. As we previously
        have partitioned it using a single partition, only one partition
        will be returned.

            @param loop_path: Path to the loopback device
        """
        print 'Creating entries under /dev/mapper for %s loop dev' % loop_path
        try:
            cmd = 'kpartx -a %s' % loop_path
            utils.system(cmd)
            l_cmd = 'kpartx -l %s | cut -f1 -d " "' % loop_path
            device = utils.system_output(l_cmd)
        except error.CmdError, e:
            e_msg = 'Error creating entries for %s: %s' % (loop_path, e)
            raise error.AutotestError(e_msg)
        return os.path.join('/dev/mapper', device)


    def __remove_entries_partition(self):
        """
        Removes the entries under /dev/mapper for the partition associated 
        to the loopback device.
        """
        print 'Removing the entry on /dev/mapper for %s loop dev' % self.loop
        try:
            cmd = 'kpartx -d %s' % self.loop
            utils.system(cmd)
        except error.CmdError, e:
            e_msg = 'Error removing entries for loop %s: %s' % (self.loop, e)
            raise error.AutotestError(e_msg)


    def __detach_img_loop(self):
        """
        Detaches the image file from the loopback device.
        """
        print 'Detaching image %s from loop device %s' % (self.img, self.loop)
        try:
            cmd = 'losetup -d %s' % self.loop
            utils.system(cmd)
        except error.CmdError, e:
            e_msg = 'Error detaching image %s from loop device %s: %s' % \
                    (self.loop, e)
            raise error.AutotestError(e_msg)


    def __remove_disk_img(self):
        """
        Removes the disk image.
        """
        print 'Removing disk image %s' % self.img
        try:
            os.remove(self.img)
        except:
            e_msg = 'Error removing image file %s' % self.img
            raise error.AutotestError(e_msg)

