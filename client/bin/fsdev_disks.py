import sys, os, re, string
from autotest_lib.client.bin import utils, fsinfo, fsdev_mgr, partition
from autotest_lib.client.common_lib import error


fd_mgr = fsdev_mgr.FsdevManager()

# For unmounting / formatting file systems we may have to use a device name
# that is different from the real device name that we have to use to set I/O
# scheduler tunables.
_DISKPART_FILE = '/proc/partitions'

##############################################################################
#
# The 'disk_list' array returned by get_disk_list() has an entry for each
# disk drive we find on the box. Each of these entries is a map with the
# following 3 string values:
#
#     'device'      disk device name (i.e. the part after /dev/)
#     'mountpt'     disk mount path
#     'tunable'     disk name for setting scheduler tunables (/sys/block/sd??)
#
# The last value is an integer that indicates the current mount status
# of the drive:
#
#     'mounted'     0 = not currently mounted
#                   1 = mounted r/w on the expected path
#                  -1 = mounted readonly or at an unexpected path
#
# When the 'std_mounts_only' argument is True we don't include drives
# mounted on 'unusual' mount points in the result.
#
##############################################################################

def get_disk_list(std_mounts_only=True):

    # Get hold of the currently mounted file systems
    mounts = utils.system_output('mount').splitlines()

    # Grab all the interesting disk partition names from /proc/partitions,
    # and build up the table of drives present in the system.
    hd_list   = []
    hd_regexp = re.compile("([hs]d[a-z]+3)$")

    partfile  = open(_DISKPART_FILE)
    for partline in partfile:
        parts = partline.strip().split()
        if len(parts) != 4 or partline.startswith('major'):
            continue

        # Get hold of the partition name
        partname = parts[3]

        # The partition name better end with a digit
        if not partname[-1:].isdigit():
            continue

        # Process any site-specific filters on the partition name
        if not fd_mgr.use_partition(partname):
            continue

        # We need to know the IDE/SATA/... device name for setting tunables
        tunepath = fd_mgr.map_drive_name(partname)

        # Check whether the device is mounted (and how)
        mstat  = 0
        fstype = ''
        fsopts = ''
        fsmkfs = '?'

        # Prepare the full device path for matching
        chkdev  = '/dev/' + partname

        # If the partition is mounted, we'll record the mount point
        mountpt = None

        for mln in mounts:

            splt = mln.split()

            # Typical 'mount' output line looks like this (indices
            # for the split() result shown below):
            #
            #    <device> on <mount_point> type <fstp> <options>
            #    0        1  2             3    4      5

            if splt[0] == chkdev:

                # Make sure the mount point looks reasonable
                mountpt = fd_mgr.check_mount_point(partname, splt[2])
                if not mountpt:
                    mstat = -1
                    break

                # Grab the file system type and mount options
                fstype = splt[4]
                fsopts = splt[5]

                # Check for something other than a r/w mount
                if fsopts[:3] != '(rw':
                    mstat = -1
                    break

                # The drive is mounted at the 'normal' mount point
                mstat = 1

        # Does the caller only want to allow 'standard' mount points?
        if std_mounts_only and mstat < 0:
            continue

        # Was this partition mounted at all?
        if not mountpt:
            # Ask the client where we should mount this partition
            mountpt = fd_mgr.check_mount_point(partname, None)
            if not mountpt:
                # Client doesn't know where to mount partition - ignore it
                continue

        # Looks like we have a valid disk drive, add it to the list
        hd_list.append({ 'device' : partname,
                         'mountpt': mountpt,
                         'tunable': tunepath,
                         'fs_type': fstype,
                         'fs_opts': fsopts,
                         'fs_mkfs': fsmkfs,
                         'mounted': mstat })

    return hd_list


def mkfs_all_disks(job, disk_list, fs_type, fs_makeopt, fs_mnt_opt):
    """
    Prepare all the drives in 'disk_list' for testing. For each disk this means
    unmounting any mount points that use the disk, running mkfs with 'fs_type'
    as the file system type and 'fs_makeopt' as the 'mkfs' options, and finally
    remounting the freshly formatted drive using the flags in 'fs_mnt_opt'.
    """

    for disk in disk_list:

        # For now, ext4 isn't quite ready for prime time
        if fs_type == "ext4":
            fs_type = "ext4dev"

        # Grab the device and mount paths for the drive
        dev_path = os.path.join('/dev', disk["device"])
        mnt_path = disk['mountpt']

        # Create a file system instance
        try:
            fs = job.filesystem(device=dev_path, mountpoint=mnt_path)
        except:
            raise Exception("Could not create a filesystem on '%s'" % dev_path)

        # Make sure the volume is unmounted
        if disk["mounted"]:
            try:
                fs.unmount(mnt_path)
            except Exception, info:
                raise Exception("umount failed: exception = %s, args = %s" %
                                               (sys.exc_info()[0], info.args))
            except:
                raise Exception("Could not unmount device ", dev_path)

        # Is the drive already formatted with the right file system?
        skip_mkfs = match_fs(disk, dev_path, fs_type, fs_makeopt)

        # Next step is to create a fresh file system (if we need to)
        try:
            if not skip_mkfs:
                fs.mkfs(fstype = fs_type, args = fs_makeopt)
        except:
            raise Exception("Could not 'mkfs " + "-t " + fs_type + " " +
                                       fs_makeopt + " " + dev_path + "'")

        # Mount the drive with the appropriate FS options
        try:
            opts = ""
            if fs_mnt_opt != "":
                opts += " -o " + fs_mnt_opt
            fs.mount(mountpoint = mnt_path, fstype = fs_type, args = opts)
        except NameError, info:
            raise Exception("mount name error: %s" % info)
        except Exception, info:
            raise Exception("mount failed: exception = %s, args = %s" %
                                             (type(info), info.args))

        # If we skipped mkfs we need to wipe the partition clean
        if skip_mkfs:
            fs.wipe()

        # Record the new file system type and options in the disk list
        disk["mounted"] = True
        disk["fs_type"] = fs_type
        disk["fs_mkfs"] = fs_makeopt
        disk["fs_opts"] = fs_mnt_opt

    # Try to wipe the file system slate clean
    utils.drop_caches()


# XXX(gps): Remove this code once refactoring is complete to get rid of these
# nasty test description strings.
def _legacy_str_to_test_flags(fs_desc_string):
    """Convert a legacy FS_LIST string into a partition.FsOptions instance."""
    match = re.search('(.*?)/(.*?)/(.*?)/(.*)$', fs_desc_string.strip())
    if not match:
        raise ValueError('unrecognized FS list entry %r' % fs_desc_string)

    flags_obj = partition.FsOptions(fstype=match.group(1).strip(),
                                    mkfs_flags=match.group(2).strip(),
                                    mount_options=match.group(3).strip(),
                                    fs_tag=match.group(4).strip())
    return flags_obj


def prepare_disks(job, fs_desc, disk1_only=False, disk_list=None):
    """
    Prepare drive(s) to contain the file system type / options given in the
    description line 'fs_desc'. When 'disk_list' is not None, we prepare all
    the drives in that list; otherwise we pick the first available data drive
    (which is usually hdc3) and prepare just that one drive.

    Args:
      fs_desc: A partition.FsOptions instance describing the test -OR- a
          legacy string describing the same in '/' separated format:
              'fstype / mkfs opts / mount opts / short name'.
      disk1_only: Boolean, defaults to False.  If True, only test the first
          disk.
      disk_list: A list of disks to prepare.  If None is given we default to
          asking get_disk_list().
    Returns:
      (mount path of the first disk, short name of the test, list of disks)
      OR (None, '', None) if no fs_desc was given.
    """

    # Special case - do nothing if caller passes no description.
    if not fs_desc:
        return (None, '', None)

    if not isinstance(fs_desc, partition.FsOptions):
        fs_desc = _legacy_str_to_test_flags(fs_desc)

    # If no disk list was given, we'll get it ourselves
    if not disk_list:
        disk_list = get_disk_list()

    # Make sure we have the appropriate 'mkfs' binary for the file system
    mkfs_bin = 'mkfs.' + fs_desc.filesystem
    if fs_desc.filesystem == 'ext4':
        mkfs_bin = 'mkfs.ext4dev'

    try:
        utils.system('which ' + mkfs_bin)
    except Exception:
        try:
            mkfs_bin = os.path.join(job.toolsdir, mkfs_bin)
            utils.system('cp -ufp %s /sbin' % mkfs_bin)
        except Exception:
            raise error.TestError('No mkfs binary available for ' +
                                  fs_desc.filesystem)

    # For 'ext4' we need to add '-E test_fs' to the mkfs options
    if fs_desc.filesystem == 'ext4':
        fs_desc.mkfs_flags += ' -E test_fs'

    # If the caller only needs one drive, grab the first one only
    if disk1_only:
        disk_list = disk_list[0:1]

    # We have all the info we need to format the drives
    mkfs_all_disks(job, disk_list, fs_desc.filesystem,
                   fs_desc.mkfs_flags, fs_desc.mount_options)

    # Return(mount path of the first disk, test tag value, disk_list)
    return (disk_list[0]['mountpt'], fs_desc.fs_tag, disk_list)


def restore_disks(job, restore=False, disk_list=None):
    """
    Restore ext2 on the drives in 'disk_list' if 'restore' is True; when
    disk_list is None, we do nothing.
    """

    if restore and disk_list is not None:
        prepare_disks(job, 'ext2 / -q -i20480 -m1 / / restore_ext2',
                           disk1_only=False,
                           disk_list=disk_list)


def wipe_disks(job, disk_list):
    """
    Wipe all of the drives in 'disk_list' using the 'wipe' functionality
    in the filesystem class.
    """
    for disk in disk_list:
        partition.wipe_filesystem(job, disk['mountpt'])


def match_fs(disk, dev_path, fs_type, fs_makeopt):
    """
    Matches the user provided fs_type and fs_makeopt with the current disk.
    """
    if disk["fs_type"] != fs_type:
        return False
    elif disk["fs_mkfs"] == fs_makeopt:
        # No need to mkfs the volume, we only need to remount it
        return True
    elif fsinfo.match_mkfs_option(fs_type, dev_path, fs_makeopt):
        if disk["fs_mkfs"] != '?':
            raise Exception("mkfs option strings differ but auto-detection"
                            " code thinks they're identical")
        else:
            return True
    else:
        return False


##############################################################################

# The following variables/methods are used to invoke fsdev in 'library' mode

FSDEV_JOB = None
FSDEV_FS_DESC = None
FSDEV_RESTORE = None
FSDEV_PREP_CNT = 0
FSDEV_DISK1_ONLY = None
FSDEV_DISKLIST = None

def use_fsdev_lib(fs_desc, disk1_only, reinit_disks):
    """
    Called from the control file to indicate that fsdev is to be used.
    """

    global FSDEV_FS_DESC
    global FSDEV_RESTORE
    global FSDEV_DISK1_ONLY
    global FSDEV_PREP_CNT

    # This is a bit tacky - we simply save the arguments in global variables
    FSDEV_FS_DESC    = fs_desc
    FSDEV_DISK1_ONLY = disk1_only
    FSDEV_RESTORE    = reinit_disks

    # We need to keep track how many times 'prepare' is called
    FSDEV_PREP_CNT   = 0


def prepare_fsdev(job):
    """
    Called from the test file to get the necessary drive(s) ready; return
    a pair of values: the absolute path to the first drive's mount point
    plus the complete disk list (which is useful for tests that need to
    use more than one drive).
    """

    global FSDEV_JOB
    global FSDEV_DISKLIST
    global FSDEV_PREP_CNT

    if not FSDEV_FS_DESC:
        return (None, None)

    # Avoid preparing the same thing more than once
    FSDEV_PREP_CNT += 1
    if FSDEV_PREP_CNT > 1:
        return (FSDEV_DISKLIST[0]['mountpt'],FSDEV_DISKLIST)

    FSDEV_JOB = job

    (path,toss,disks) = prepare_disks(job, fs_desc    = FSDEV_FS_DESC,
                                           disk1_only = FSDEV_DISK1_ONLY,
                                           disk_list  = None)
    FSDEV_DISKLIST = disks
    return (path,disks)


def finish_fsdev(force_cleanup=False):
    """
    This method can be called from the test file to optionally restore
    all the drives used by the test to a standard ext2 format. Note that
    if use_fsdev_lib() was invoked with 'reinit_disks' not set to True,
    this method does nothing. Note also that only fsdev "server-side"
    dynamic control files should ever set force_cleanup to True.
    """

    if FSDEV_PREP_CNT == 1 or force_cleanup:
        restore_disks(job       = FSDEV_JOB,
                      restore   = FSDEV_RESTORE,
                      disk_list = FSDEV_DISKLIST)


##############################################################################

class fsdev_disks:
    """
    Disk drive handling class used for file system development
    """

    def __init__(self, job):
        self.job = job


    # Some clients need to access the 'fsdev manager' instance directly
    def get_fsdev_mgr(self):
        return fd_mgr


    def config_sched_tunables(self, desc_file):

        # Parse the file that describes the scheduler tunables and their paths
        self.tune_loc = eval(open(desc_file).read())

        # Figure out what kernel we're running on
        kver = utils.system_output('uname -r')
        kver = re.match("([0-9]+\.[0-9]+\.[0-9]+).*", kver)
        kver = kver.group(1)

        # Make sure we know how to handle the kernel we're running on
        tune_files = self.tune_loc[kver]
        if tune_files is None:
            raise Exception("Scheduler tunables not available for kernel " +
                            kver)

        # Save the kernel version for later
        self.kernel_ver = kver

        # For now we always use 'anticipatory'
        tune_paths = tune_files["anticipatory"]

        # Create a dictionary out of the tunables array
        self.tune_loc = {}
        for tx in range(len(tune_paths)):
            # Grab the next tunable path from the array
            tpath = tune_paths[tx]

            # Strip any leading directory names
            tuner = tpath
            while 1:
                slash = tuner.find("/")
                if slash < 0:
                    break
                tuner = tuner[slash+1:]

            # Add mapping to the dictionary
            self.tune_loc[tuner] = tpath


    def load_sched_tunable_values(self, val_file):

        # Prepare the array of tunable values
        self.tune_list = []

        # Read the config parameters and find the values that match our kernel
        for cfgline in open(val_file):
            cfgline = cfgline.strip()
            if len(cfgline) == 0:
                continue
            if cfgline.startswith("#"):
                continue
            if cfgline.startswith("tune[") == 0:
                raise Exception("Config entry not recognized: " + cfgline)
            endKV = cfgline.find("]:")
            if endKV < 0:
                raise Exception("Config entry missing closing bracket: "
                                                                     + cfgline)
            if cfgline[5:endKV] != self.kernel_ver[0:endKV-5]:
                continue

            tune_parm = cfgline[endKV+2:].strip()
            equal = tune_parm.find("=")
            if equal < 1 or equal == len(tune_parm) - 1:
                raise Exception("Config entry doesn't have 'parameter=value' :"
                                                                     + cfgline)

            tune_name = tune_parm[:equal]
            tune_val  = tune_parm[equal+1:]

            # See if we have a matching entry in the path dictionary
            try:
                tune_path = self.tune_loc[tune_name]
            except:
                raise Exception("Unknown config entry: " + cfgline)

            self.tune_list.append((tune_name, tune_path, tune_val))


    def set_sched_tunables(self, disks):
        """
        Given a list of disks in the format returned by get_disk_list() above,
        set the I/O scheduler values on all the disks to the values loaded
        earlier by load_sched_tunables().
        """

        for dx in range(len(disks)):
            disk = disks[dx]['tunable']

            # Set the scheduler first before setting any other tunables
            self.set_tunable(disk, "scheduler",
                                   self.tune_loc["scheduler"],
                                   "anticipatory")

            # Now set all the tunable parameters we've been given
            for tune_desc in self.tune_list:
                self.set_tunable(disk, tune_desc[0],
                                       tune_desc[1],
                                       tune_desc[2])


    def set_tunable(self, disk, name, path, val):
        """
        Given a disk name, a path to a tunable value under _TUNE_PATH and the
        new value for the parameter, set the value and verify that the value
        has been successfully set.
        """

        fpath = partition.get_iosched_path(disk, path)

        # Things might go wrong so we'll catch exceptions
        try:

            step = "open tunable path"
            tunef = open(fpath, 'w', buffering=-1)

            step = "write new tunable value"
            tunef.write(val)

            step = "close the tunable path"
            tunef.close()

            step = "read back new tunable value"
            nval = open(fpath, 'r', buffering=-1).read().strip()

            # For 'scheduler' we need to fish out the bracketed value
            if name == "scheduler":
                nval = re.match(".*\[(.*)\].*", nval).group(1)

        except IOError, info:

            # Special case: for some reason 'max_sectors_kb' often doesn't work
            # with large values; try '128' if we haven't tried it already.
            if name == "max_sectors_kb" and info.errno == 22 and val != '128':
                self.set_tunable(disk, name, path, '128')
                return;

            # Something went wrong, probably a 'config' problem of some kind
            raise Exception("Unable to set tunable value '" + name +
                            "' at step '" + step + "': " + str(info))
        except Exception:

            # We should only ever see 'IOError' above, but just in case ...
            raise Exception("Unable to set tunable value for " + name)

        # Make sure the new value is what we expected
        if nval != val:
            raise Exception("Unable to correctly set tunable value for "
                            + name +": desired " + val + ", but found " + nval)

        return
