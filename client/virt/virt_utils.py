"""
KVM test utility functions.

@copyright: 2008-2009 Red Hat Inc.
"""

import time, string, random, socket, os, signal, re, logging, commands, cPickle
import fcntl, shelve, ConfigParser, threading, sys, UserDict, inspect, tarfile
import struct, shutil, glob, HTMLParser, urllib
from autotest.client import utils, os_dep
from autotest.client.shared import error, logging_config
from autotest.client.shared import logging_manager, git
from autotest.client.virt import virt_env_process, virt_vm
from autotest.client.shared.syncdata import SyncData, SyncListenServer
import rss_client, aexpect
import platform

try:
    import koji
    KOJI_INSTALLED = True
except ImportError:
    KOJI_INSTALLED = False

ARCH = platform.machine()
if ARCH == "ppc64":
    # From include/linux/sockios.h
    SIOCSIFHWADDR  = 0x8924
    SIOCGIFHWADDR  = 0x8927
    SIOCSIFFLAGS   = 0x8914
    SIOCGIFINDEX   = 0x8933
    SIOCBRADDIF    = 0x89a2
    # From linux/include/linux/if_tun.h
    TUNSETIFF      = 0x800454ca
    TUNGETIFF      = 0x400454d2
    TUNGETFEATURES = 0x400454cf
    IFF_TAP        = 0x2
    IFF_NO_PI      = 0x1000
    IFF_VNET_HDR   = 0x4000
    # From linux/include/linux/if.h
    IFF_UP = 0x1
else:
    # From include/linux/sockios.h
    SIOCSIFHWADDR = 0x8924
    SIOCGIFHWADDR = 0x8927
    SIOCSIFFLAGS = 0x8914
    SIOCGIFINDEX = 0x8933
    SIOCBRADDIF = 0x89a2
    # From linux/include/linux/if_tun.h
    TUNSETIFF = 0x400454ca
    TUNGETIFF = 0x800454d2
    TUNGETFEATURES = 0x800454cf
    IFF_TAP = 0x0002
    IFF_NO_PI = 0x1000
    IFF_VNET_HDR = 0x4000
    # From linux/include/linux/if.h
    IFF_UP = 0x1


def _lock_file(filename):
    f = open(filename, "w")
    fcntl.lockf(f, fcntl.LOCK_EX)
    return f


def _unlock_file(f):
    fcntl.lockf(f, fcntl.LOCK_UN)
    f.close()


def is_vm(obj):
    """
    Tests whether a given object is a VM object.

    @param obj: Python object.
    """
    return obj.__class__.__name__ == "VM"


class NetError(Exception):
    pass


class TAPModuleError(NetError):
    def __init__(self, devname, action="open", details=None):
        NetError.__init__(self, devname)
        self.devname = devname
        self.details = details

    def __str__(self):
        e_msg = "Can't %s %s" % (self.action, self.devname)
        if self.details is not None:
            e_msg += " : %s" % self.details
        return e_msg


class TAPNotExistError(NetError):
    def __init__(self, ifname):
        NetError.__init__(self, ifname)
        self.ifname = ifname

    def __str__(self):
        return "Interface %s does not exist" % self.ifname


class TAPCreationError(NetError):
    def __init__(self, ifname, details=None):
        NetError.__init__(self, ifname, details)
        self.ifname = ifname
        self.details = details

    def __str__(self):
        e_msg = "Cannot create TAP device %s" % self.ifname
        if self.details is not None:
            e_msg += ": %s" % self.details
        return e_msg


class TAPBringUpError(NetError):
    def __init__(self, ifname):
        NetError.__init__(self, ifname)
        self.ifname = ifname

    def __str__(self):
        return "Cannot bring up TAP %s" % self.ifname


class BRAddIfError(NetError):
    def __init__(self, ifname, brname, details):
        NetError.__init__(self, ifname, brname, details)
        self.ifname = ifname
        self.brname = brname
        self.details = details

    def __str__(self):
        return ("Can not add if %s to bridge %s: %s" %
                (self.ifname, self.brname, self.details))


class HwAddrSetError(NetError):
    def __init__(self, ifname, mac):
        NetError.__init__(self, ifname, mac)
        self.ifname = ifname
        self.mac = mac

    def __str__(self):
        return "Can not set mac %s to interface %s" % (self.mac, self.ifname)


class HwAddrGetError(NetError):
    def __init__(self, ifname):
        NetError.__init__(self, ifname)
        self.ifname = ifname

    def __str__(self):
        return "Can not get mac of interface %s" % self.ifname


class Env(UserDict.IterableUserDict):
    """
    A dict-like object containing global objects used by tests.
    """
    def __init__(self, filename=None, version=0):
        """
        Create an empty Env object or load an existing one from a file.

        If the version recorded in the file is lower than version, or if some
        error occurs during unpickling, or if filename is not supplied,
        create an empty Env object.

        @param filename: Path to an env file.
        @param version: Required env version (int).
        """
        UserDict.IterableUserDict.__init__(self)
        empty = {"version": version}
        if filename:
            self._filename = filename
            try:
                if os.path.isfile(filename):
                    f = open(filename, "r")
                    env = cPickle.load(f)
                    f.close()
                    if env.get("version", 0) >= version:
                        self.data = env
                    else:
                        logging.warn("Incompatible env file found. Not using it.")
                        self.data = empty
                else:
                    # No previous env file found, proceed...
                    self.data = empty
            # Almost any exception can be raised during unpickling, so let's
            # catch them all
            except Exception, e:
                logging.warn(e)
                self.data = empty
        else:
            self.data = empty


    def save(self, filename=None):
        """
        Pickle the contents of the Env object into a file.

        @param filename: Filename to pickle the dict into.  If not supplied,
                use the filename from which the dict was loaded.
        """
        filename = filename or self._filename
        f = open(filename, "w")
        cPickle.dump(self.data, f)
        f.close()


    def get_all_vms(self):
        """
        Return a list of all VM objects in this Env object.
        """
        return [o for o in self.values() if is_vm(o)]


    def get_vm(self, name):
        """
        Return a VM object by its name.

        @param name: VM name.
        """
        return self.get("vm__%s" % name)


    def register_vm(self, name, vm):
        """
        Register a VM in this Env object.

        @param name: VM name.
        @param vm: VM object.
        """
        self["vm__%s" % name] = vm


    def unregister_vm(self, name):
        """
        Remove a given VM.

        @param name: VM name.
        """
        del self["vm__%s" % name]


    def register_syncserver(self, port, server):
        """
        Register a Sync Server in this Env object.

        @param port: Sync Server port.
        @param server: Sync Server object.
        """
        self["sync__%s" % port] = server


    def unregister_syncserver(self, port):
        """
        Remove a given Sync Server.

        @param port: Sync Server port.
        """
        del self["sync__%s" % port]


    def get_syncserver(self, port):
        """
        Return a Sync Server object by its port.

        @param port: Sync Server port.
        """
        return self.get("sync__%s" % port)


    def register_installer(self, installer):
        """
        Register a installer that was just run

        The installer will be available for other tests, so that
        information about the installed KVM modules and qemu-kvm can be used by
        them.
        """
        self['last_installer'] = installer


    def previous_installer(self):
        """
        Return the last installer that was registered
        """
        return self.get('last_installer')


class Params(UserDict.IterableUserDict):
    """
    A dict-like object passed to every test.
    """
    def objects(self, key):
        """
        Return the names of objects defined using a given key.

        @param key: The name of the key whose value lists the objects
                (e.g. 'nics').
        """
        return self.get(key, "").split()


    def object_params(self, obj_name):
        """
        Return a dict-like object containing the parameters of an individual
        object.

        This method behaves as follows: the suffix '_' + obj_name is removed
        from all key names that have it.  Other key names are left unchanged.
        The values of keys with the suffix overwrite the values of their
        suffixless versions.

        @param obj_name: The name of the object (objects are listed by the
                objects() method).
        """
        suffix = "_" + obj_name
        new_dict = self.copy()
        for key in self:
            if key.endswith(suffix):
                new_key = key.split(suffix)[0]
                new_dict[new_key] = self[key]
        return new_dict


# Functions related to MAC/IP addresses

def _open_mac_pool(lock_mode):
    lock_file = open("/tmp/mac_lock", "w+")
    fcntl.lockf(lock_file, lock_mode)
    pool = shelve.open("/tmp/address_pool")
    return pool, lock_file


def _close_mac_pool(pool, lock_file):
    pool.close()
    fcntl.lockf(lock_file, fcntl.LOCK_UN)
    lock_file.close()


def _generate_mac_address_prefix(mac_pool):
    """
    Generate a random MAC address prefix and add it to the MAC pool dictionary.
    If there's a MAC prefix there already, do not update the MAC pool and just
    return what's in there. By convention we will set KVM autotest MAC
    addresses to start with 0x9a.

    @param mac_pool: The MAC address pool object.
    @return: The MAC address prefix.
    """
    if "prefix" in mac_pool:
        prefix = mac_pool["prefix"]
    else:
        r = random.SystemRandom()
        prefix = "9a:%02x:%02x:%02x:" % (r.randint(0x00, 0xff),
                                         r.randint(0x00, 0xff),
                                         r.randint(0x00, 0xff))
        mac_pool["prefix"] = prefix
    return prefix


def generate_mac_address(vm_instance, nic_index):
    """
    Randomly generate a MAC address and add it to the MAC address pool.

    Try to generate a MAC address based on a randomly generated MAC address
    prefix and add it to a persistent dictionary.
    key = VM instance + NIC index, value = MAC address
    e.g. {'20100310-165222-Wt7l:0': '9a:5d:94:6a:9b:f9'}

    @param vm_instance: The instance attribute of a VM.
    @param nic_index: The index of the NIC.
    @return: MAC address string.
    """
    mac_pool, lock_file = _open_mac_pool(fcntl.LOCK_EX)
    key = "%s:%s" % (vm_instance, nic_index)
    if key in mac_pool:
        mac = mac_pool[key]
    else:
        prefix = _generate_mac_address_prefix(mac_pool)
        r = random.SystemRandom()
        while key not in mac_pool:
            mac = prefix + "%02x:%02x" % (r.randint(0x00, 0xff),
                                          r.randint(0x00, 0xff))
            if mac in mac_pool.values():
                continue
            mac_pool[key] = mac
    _close_mac_pool(mac_pool, lock_file)
    return mac


def free_mac_address(vm_instance, nic_index):
    """
    Remove a MAC address from the address pool.

    @param vm_instance: The instance attribute of a VM.
    @param nic_index: The index of the NIC.
    """
    mac_pool, lock_file = _open_mac_pool(fcntl.LOCK_EX)
    key = "%s:%s" % (vm_instance, nic_index)
    if key in mac_pool:
        del mac_pool[key]
    _close_mac_pool(mac_pool, lock_file)


def set_mac_address(vm_instance, nic_index, mac):
    """
    Set a MAC address in the pool.

    @param vm_instance: The instance attribute of a VM.
    @param nic_index: The index of the NIC.
    """
    mac_pool, lock_file = _open_mac_pool(fcntl.LOCK_EX)
    mac_pool["%s:%s" % (vm_instance, nic_index)] = mac
    _close_mac_pool(mac_pool, lock_file)


def get_mac_address(vm_instance, nic_index):
    """
    Return a MAC address from the pool.

    @param vm_instance: The instance attribute of a VM.
    @param nic_index: The index of the NIC.
    @return: MAC address string.
    """
    mac_pool, lock_file = _open_mac_pool(fcntl.LOCK_SH)
    mac = mac_pool.get("%s:%s" % (vm_instance, nic_index))
    _close_mac_pool(mac_pool, lock_file)
    return mac


def verify_ip_address_ownership(ip, macs, timeout=10.0):
    """
    Use arping and the ARP cache to make sure a given IP address belongs to one
    of the given MAC addresses.

    @param ip: An IP address.
    @param macs: A list or tuple of MAC addresses.
    @return: True iff ip is assigned to a MAC address in macs.
    """
    # Compile a regex that matches the given IP address and any of the given
    # MAC addresses
    mac_regex = "|".join("(%s)" % mac for mac in macs)
    regex = re.compile(r"\b%s\b.*\b(%s)\b" % (ip, mac_regex), re.IGNORECASE)

    # Check the ARP cache
    o = commands.getoutput("%s -n" % find_command("arp"))
    if regex.search(o):
        return True

    # Get the name of the bridge device for arping
    o = commands.getoutput("%s route get %s" % (find_command("ip"), ip))
    dev = re.findall("dev\s+\S+", o, re.IGNORECASE)
    if not dev:
        return False
    dev = dev[0].split()[-1]

    # Send an ARP request
    o = commands.getoutput("%s -f -c 3 -I %s %s" %
                           (find_command("arping"), dev, ip))
    return bool(regex.search(o))


# Utility functions for dealing with external processes

def find_command(cmd):
    for dir in ["/usr/local/sbin", "/usr/local/bin",
                "/usr/sbin", "/usr/bin", "/sbin", "/bin"]:
        file = os.path.join(dir, cmd)
        if os.path.exists(file):
            return file
    raise ValueError('Missing command: %s' % cmd)


def pid_exists(pid):
    """
    Return True if a given PID exists.

    @param pid: Process ID number.
    """
    try:
        os.kill(pid, 0)
        return True
    except Exception:
        return False


def safe_kill(pid, signal):
    """
    Attempt to send a signal to a given process that may or may not exist.

    @param signal: Signal number.
    """
    try:
        os.kill(pid, signal)
        return True
    except Exception:
        return False


def kill_process_tree(pid, sig=signal.SIGKILL):
    """Signal a process and all of its children.

    If the process does not exist -- return.

    @param pid: The pid of the process to signal.
    @param sig: The signal to send to the processes.
    """
    if not safe_kill(pid, signal.SIGSTOP):
        return
    children = commands.getoutput("ps --ppid=%d -o pid=" % pid).split()
    for child in children:
        kill_process_tree(int(child), sig)
    safe_kill(pid, sig)
    safe_kill(pid, signal.SIGCONT)


def check_kvm_source_dir(source_dir):
    """
    Inspects the kvm source directory and verifies its disposition. In some
    occasions build may be dependant on the source directory disposition.
    The reason why the return codes are numbers is that we might have more
    changes on the source directory layout, so it's not scalable to just use
    strings like 'old_repo', 'new_repo' and such.

    @param source_dir: Source code path that will be inspected.
    """
    os.chdir(source_dir)
    has_qemu_dir = os.path.isdir('qemu')
    has_kvm_dir = os.path.isdir('kvm')
    if has_qemu_dir:
        logging.debug("qemu directory detected, source dir layout 1")
        return 1
    if has_kvm_dir and not has_qemu_dir:
        logging.debug("kvm directory detected, source dir layout 2")
        return 2
    else:
        raise error.TestError("Unknown source dir layout, cannot proceed.")


# Functions for handling virtual machine image files

def get_image_blkdebug_filename(params, root_dir):
    """
    Generate an blkdebug file path from params and root_dir.

    blkdebug files allow error injection in the block subsystem.

    @param params: Dictionary containing the test parameters.
    @param root_dir: Base directory for relative filenames.

    @note: params should contain:
           blkdebug -- the name of the debug file.
    """
    blkdebug_name = params.get("drive_blkdebug", None)
    if blkdebug_name is not None:
        blkdebug_filename = get_path(root_dir, blkdebug_name)
    else:
        blkdebug_filename = None
    return blkdebug_filename


def get_image_filename(params, root_dir):
    """
    Generate an image path from params and root_dir.

    @param params: Dictionary containing the test parameters.
    @param root_dir: Base directory for relative filenames.

    @note: params should contain:
           image_name -- the name of the image file, without extension
           image_format -- the format of the image (qcow2, raw etc)
    @raise VMDeviceError: When no matching disk found (in indirect method).
    """
    image_name = params.get("image_name", "image")
    indirect_image_select = params.get("indirect_image_select")
    if indirect_image_select:
        re_name = image_name
        indirect_image_select = int(indirect_image_select)
        matching_images = utils.system_output("ls -1d %s" % re_name)
        matching_images = sorted(matching_images.split('\n'))
        if matching_images[-1] == '':
            matching_images = matching_images[:-1]
        try:
            image_name = matching_images[indirect_image_select]
        except IndexError:
            raise virt_vm.VMDeviceError("No matching disk found for "
                                        "name = '%s', matching = '%s' and "
                                        "selector = '%s'" %
                                        (re_name, matching_images,
                                         indirect_image_select))
        for protected in params.get('indirect_image_blacklist', '').split(' '):
            if re.match(protected, image_name):
                raise virt_vm.VMDeviceError("Matching disk is in blacklist. "
                                            "name = '%s', matching = '%s' and "
                                            "selector = '%s'" %
                                            (re_name, matching_images,
                                             indirect_image_select))
    image_format = params.get("image_format", "qcow2")
    if params.get("image_raw_device") == "yes":
        return image_name
    if image_format:
        image_filename = "%s.%s" % (image_name, image_format)
    else:
        image_filename = image_name
    image_filename = get_path(root_dir, image_filename)
    return image_filename


def clone_image(params, vm_name, image_name, root_dir):
    """
    Clone master image to vm specific file.

    @param params: Dictionary containing the test parameters.
    @param vm_name: Vm name.
    @param image_name: Master image name.
    @param root_dir: Base directory for relative filenames.
    """
    if not params.get("image_name_%s_%s" % (image_name, vm_name)):
        m_image_name = params.get("image_name", "image")
        vm_image_name = "%s_%s" % (m_image_name, vm_name)
        if params.get("clone_master", "yes") == "yes":
            image_params = params.object_params(image_name)
            image_params["image_name"] = vm_image_name

            m_image_fn = get_image_filename(params, root_dir)
            image_fn = get_image_filename(image_params, root_dir)

            logging.info("Clone master image for vms.")
            utils.run(params.get("image_clone_commnad") % (m_image_fn,
                                                           image_fn))

        params["image_name_%s_%s" % (image_name, vm_name)] = vm_image_name


def rm_image(params, vm_name, image_name, root_dir):
    """
    Remove vm specific file.

    @param params: Dictionary containing the test parameters.
    @param vm_name: Vm name.
    @param image_name: Master image name.
    @param root_dir: Base directory for relative filenames.
    """
    if params.get("image_name_%s_%s" % (image_name, vm_name)):
        m_image_name = params.get("image_name", "image")
        vm_image_name = "%s_%s" % (m_image_name, vm_name)
        if params.get("clone_master", "yes") == "yes":
            image_params = params.object_params(image_name)
            image_params["image_name"] = vm_image_name

            image_fn = get_image_filename(image_params, root_dir)

            logging.debug("Removing vm specific image file %s", image_fn)
            if os.path.exists(image_fn):
                utils.run(params.get("image_remove_commnad") % (image_fn))
            else:
                logging.debug("Image file %s not found", image_fn)


def create_image(params, root_dir):
    """
    Create an image using qemu_image.

    @param params: Dictionary containing the test parameters.
    @param root_dir: Base directory for relative filenames.

    @note: params should contain:
           image_name -- the name of the image file, without extension
           image_format -- the format of the image (qcow2, raw etc)
           image_cluster_size (optional) -- the cluster size for the image
           image_size -- the requested size of the image (a string
           qemu-img can understand, such as '10G')
           create_with_dd -- use dd to create the image (raw format only)
    """
    format = params.get("image_format", "qcow2")
    image_filename = get_image_filename(params, root_dir)
    size = params.get("image_size", "10G")
    if params.get("create_with_dd") == "yes" and format == "raw":
        # maps K,M,G,T => (count, bs)
        human = {'K': (1, 1),
                 'M': (1, 1024),
                 'G': (1024, 1024),
                 'T': (1024, 1048576),
                }
        if human.has_key(size[-1]):
            block_size = human[size[-1]][1]
            size = int(size[:-1]) * human[size[-1]][0]
        qemu_img_cmd = ("dd if=/dev/zero of=%s count=%s bs=%sK"
                        % (image_filename, size, block_size))
    else:
        qemu_img_cmd = get_path(root_dir,
                                params.get("qemu_img_binary", "qemu-img"))
        qemu_img_cmd += " create"

        qemu_img_cmd += " -f %s" % format

        image_cluster_size = params.get("image_cluster_size", None)
        if image_cluster_size is not None:
            qemu_img_cmd += " -o cluster_size=%s" % image_cluster_size

        qemu_img_cmd += " %s" % image_filename

        qemu_img_cmd += " %s" % size

    utils.system(qemu_img_cmd)
    return image_filename


def remove_image(params, root_dir):
    """
    Remove an image file.

    @param params: A dict
    @param root_dir: Base directory for relative filenames.

    @note: params should contain:
           image_name -- the name of the image file, without extension
           image_format -- the format of the image (qcow2, raw etc)
    """
    image_filename = get_image_filename(params, root_dir)
    logging.debug("Removing image file %s", image_filename)
    if os.path.exists(image_filename):
        os.unlink(image_filename)
    else:
        logging.debug("Image file %s not found", image_filename)


def check_image(params, root_dir):
    """
    Check an image using the appropriate tools for each virt backend.

    @param params: Dictionary containing the test parameters.
    @param root_dir: Base directory for relative filenames.

    @note: params should contain:
           image_name -- the name of the image file, without extension
           image_format -- the format of the image (qcow2, raw etc)

    @raise VMImageCheckError: In case qemu-img check fails on the image.
    """
    vm_type = params.get("vm_type")
    if vm_type == 'kvm':
        image_filename = get_image_filename(params, root_dir)
        logging.debug("Checking image file %s", image_filename)
        qemu_img_cmd = get_path(root_dir,
                                params.get("qemu_img_binary", "qemu-img"))
        image_is_qcow2 = params.get("image_format") == 'qcow2'
        if os.path.exists(image_filename) and image_is_qcow2:
            # Verifying if qemu-img supports 'check'
            q_result = utils.run(qemu_img_cmd, ignore_status=True)
            q_output = q_result.stdout
            check_img = True
            if not "check" in q_output:
                logging.error("qemu-img does not support 'check', "
                              "skipping check")
                check_img = False
            if not "info" in q_output:
                logging.error("qemu-img does not support 'info', "
                              "skipping check")
                check_img = False
            if check_img:
                try:
                    utils.system("%s info %s" % (qemu_img_cmd, image_filename))
                except error.CmdError:
                    logging.error("Error getting info from image %s",
                                  image_filename)

                cmd_result = utils.run("%s check %s" %
                                       (qemu_img_cmd, image_filename),
                                       ignore_status=True)
                # Error check, large chances of a non-fatal problem.
                # There are chances that bad data was skipped though
                if cmd_result.exit_status == 1:
                    for e_line in cmd_result.stdout.splitlines():
                        logging.error("[stdout] %s", e_line)
                    for e_line in cmd_result.stderr.splitlines():
                        logging.error("[stderr] %s", e_line)
                    if params.get("backup_image_on_check_error", "no") == "yes":
                        backup_image(params, root_dir, 'backup', False)
                    raise error.TestWarn("qemu-img check error. Some bad data "
                                         "in the image may have gone unnoticed")
                # Exit status 2 is data corruption for sure, so fail the test
                elif cmd_result.exit_status == 2:
                    for e_line in cmd_result.stdout.splitlines():
                        logging.error("[stdout] %s", e_line)
                    for e_line in cmd_result.stderr.splitlines():
                        logging.error("[stderr] %s", e_line)
                    if params.get("backup_image_on_check_error", "no") == "yes":
                        backup_image(params, root_dir, 'backup', False)
                    raise virt_vm.VMImageCheckError(image_filename)
                # Leaked clusters, they are known to be harmless to data
                # integrity
                elif cmd_result.exit_status == 3:
                    raise error.TestWarn("Leaked clusters were noticed during "
                                         "image check. No data integrity "
                                         "problem was found though.")

                # Just handle normal operation
                if params.get("backup_image", "no") == "yes":
                    backup_image(params, root_dir, 'backup', True)

        else:
            if not os.path.exists(image_filename):
                logging.debug("Image file %s not found, skipping check",
                              image_filename)
            elif not image_is_qcow2:
                logging.debug("Image file %s not qcow2, skipping check",
                              image_filename)


def backup_image(params, root_dir, action, good=True):
    """
    Backup or restore a disk image, depending on the action chosen.

    @param params: Dictionary containing the test parameters.
    @param root_dir: Base directory for relative filenames.
    @param action: Whether we want to backup or restore the image.
    @param good: If we are backing up a good image(we want to restore it) or
            a bad image (we are saving a bad image for posterior analysis).

    @note: params should contain:
           image_name -- the name of the image file, without extension
           image_format -- the format of the image (qcow2, raw etc)
    """
    def backup_raw_device(src, dst):
        utils.system("dd if=%s of=%s bs=4k conv=sync" % (src, dst))

    def backup_image_file(src, dst):
        logging.debug("Copying %s -> %s", src, dst)
        shutil.copy(src, dst)

    def get_backup_name(filename, backup_dir, good):
        if not os.path.isdir(backup_dir):
            os.makedirs(backup_dir)
        basename = os.path.basename(filename)
        if good:
            backup_filename = "%s.backup" % basename
        else:
            backup_filename = ("%s.bad.%s" %
                               (basename, generate_random_string(4)))
        return os.path.join(backup_dir, backup_filename)


    image_filename = get_image_filename(params, root_dir)
    backup_dir = params.get("backup_dir")
    if params.get('image_raw_device') == 'yes':
        iname = "raw_device"
        iformat = params.get("image_format", "qcow2")
        ifilename = "%s.%s" % (iname, iformat)
        ifilename = get_path(root_dir, ifilename)
        image_filename_backup = get_backup_name(ifilename, backup_dir, good)
        backup_func = backup_raw_device
    else:
        image_filename_backup = get_backup_name(image_filename, backup_dir,
                                                good)
        backup_func = backup_image_file

    if action == 'backup':
        image_dir = os.path.dirname(image_filename)
        image_dir_disk_free = utils.freespace(image_dir)
        image_filename_size = os.path.getsize(image_filename)
        image_filename_backup_size = 0
        if os.path.isfile(image_filename_backup):
            image_filename_backup_size = os.path.getsize(image_filename_backup)
        disk_free = image_dir_disk_free + image_filename_backup_size
        minimum_disk_free = 1.2 * image_filename_size
        if disk_free < minimum_disk_free:
            image_dir_disk_free_gb = float(image_dir_disk_free) / 10**9
            minimum_disk_free_gb = float(minimum_disk_free) / 10**9
            logging.error("Dir %s has %.1f GB free, less than the minimum "
                          "required to store a backup, defined to be 120%% "
                          "of the backup size, %.1f GB. Skipping backup...",
                          image_dir, image_dir_disk_free_gb,
                          minimum_disk_free_gb)
            return
        if good:
            # In case of qemu-img check return 1, we will make 2 backups, one
            # for investigation and other, to use as a 'pristine' image for
            # further tests
            state = 'good'
        else:
            state = 'bad'
        logging.info("Backing up %s image file %s", state, image_filename)
        src, dst = image_filename, image_filename_backup
    elif action == 'restore':
        if not os.path.isfile(image_filename_backup):
            logging.error('Image backup %s not found, skipping restore...',
                          image_filename_backup)
            return
        logging.info("Restoring image file %s from backup",
                     image_filename)
        src, dst = image_filename_backup, image_filename

    backup_func(src, dst)


# Functions and classes used for logging into guests and transferring files

class LoginError(Exception):
    def __init__(self, msg, output):
        Exception.__init__(self, msg, output)
        self.msg = msg
        self.output = output

    def __str__(self):
        return "%s    (output: %r)" % (self.msg, self.output)


class LoginAuthenticationError(LoginError):
    pass


class LoginTimeoutError(LoginError):
    def __init__(self, output):
        LoginError.__init__(self, "Login timeout expired", output)


class LoginProcessTerminatedError(LoginError):
    def __init__(self, status, output):
        LoginError.__init__(self, None, output)
        self.status = status

    def __str__(self):
        return ("Client process terminated    (status: %s,    output: %r)" %
                (self.status, self.output))


class LoginBadClientError(LoginError):
    def __init__(self, client):
        LoginError.__init__(self, None, None)
        self.client = client

    def __str__(self):
        return "Unknown remote shell client: %r" % self.client


class SCPError(Exception):
    def __init__(self, msg, output):
        Exception.__init__(self, msg, output)
        self.msg = msg
        self.output = output

    def __str__(self):
        return "%s    (output: %r)" % (self.msg, self.output)


class SCPAuthenticationError(SCPError):
    pass


class SCPAuthenticationTimeoutError(SCPAuthenticationError):
    def __init__(self, output):
        SCPAuthenticationError.__init__(self, "Authentication timeout expired",
                                        output)


class SCPTransferTimeoutError(SCPError):
    def __init__(self, output):
        SCPError.__init__(self, "Transfer timeout expired", output)


class SCPTransferFailedError(SCPError):
    def __init__(self, status, output):
        SCPError.__init__(self, None, output)
        self.status = status

    def __str__(self):
        return ("SCP transfer failed    (status: %s,    output: %r)" %
                (self.status, self.output))


def _remote_login(session, username, password, prompt, timeout=10, debug=False):
    """
    Log into a remote host (guest) using SSH or Telnet.  Wait for questions
    and provide answers.  If timeout expires while waiting for output from the
    child (e.g. a password prompt or a shell prompt) -- fail.

    @brief: Log into a remote host (guest) using SSH or Telnet.

    @param session: An Expect or ShellSession instance to operate on
    @param username: The username to send in reply to a login prompt
    @param password: The password to send in reply to a password prompt
    @param prompt: The shell prompt that indicates a successful login
    @param timeout: The maximal time duration (in seconds) to wait for each
            step of the login procedure (i.e. the "Are you sure" prompt, the
            password prompt, the shell prompt, etc)
    @raise LoginTimeoutError: If timeout expires
    @raise LoginAuthenticationError: If authentication fails
    @raise LoginProcessTerminatedError: If the client terminates during login
    @raise LoginError: If some other error occurs
    """
    password_prompt_count = 0
    login_prompt_count = 0

    while True:
        try:
            match, text = session.read_until_last_line_matches(
                [r"[Aa]re you sure", r"[Pp]assword:\s*$", r"[Ll]ogin:\s*$",
                 r"[Cc]onnection.*closed", r"[Cc]onnection.*refused",
                 r"[Pp]lease wait", r"[Ww]arning", prompt],
                timeout=timeout, internal_timeout=0.5)
            if match == 0:  # "Are you sure you want to continue connecting"
                if debug:
                    logging.debug("Got 'Are you sure...', sending 'yes'")
                session.sendline("yes")
                continue
            elif match == 1:  # "password:"
                if password_prompt_count == 0:
                    if debug:
                        logging.debug("Got password prompt, sending '%s'", password)
                    session.sendline(password)
                    password_prompt_count += 1
                    continue
                else:
                    raise LoginAuthenticationError("Got password prompt twice",
                                                   text)
            elif match == 2:  # "login:"
                if login_prompt_count == 0 and password_prompt_count == 0:
                    if debug:
                        logging.debug("Got username prompt; sending '%s'", username)
                    session.sendline(username)
                    login_prompt_count += 1
                    continue
                else:
                    if login_prompt_count > 0:
                        msg = "Got username prompt twice"
                    else:
                        msg = "Got username prompt after password prompt"
                    raise LoginAuthenticationError(msg, text)
            elif match == 3:  # "Connection closed"
                raise LoginError("Client said 'connection closed'", text)
            elif match == 4:  # "Connection refused"
                raise LoginError("Client said 'connection refused'", text)
            elif match == 5:  # "Please wait"
                if debug:
                    logging.debug("Got 'Please wait'")
                timeout = 30
                continue
            elif match == 6:  # "Warning added RSA"
                if debug:
                    logging.debug("Got 'Warning added RSA to known host list")
                continue
            elif match == 7:  # prompt
                if debug:
                    logging.debug("Got shell prompt -- logged in")
                break
        except aexpect.ExpectTimeoutError, e:
            raise LoginTimeoutError(e.output)
        except aexpect.ExpectProcessTerminatedError, e:
            raise LoginProcessTerminatedError(e.status, e.output)


def remote_login(client, host, port, username, password, prompt, linesep="\n",
                 log_filename=None, timeout=10):
    """
    Log into a remote host (guest) using SSH/Telnet/Netcat.

    @param client: The client to use ('ssh', 'telnet' or 'nc')
    @param host: Hostname or IP address
    @param port: Port to connect to
    @param username: Username (if required)
    @param password: Password (if required)
    @param prompt: Shell prompt (regular expression)
    @param linesep: The line separator to use when sending lines
            (e.g. '\\n' or '\\r\\n')
    @param log_filename: If specified, log all output to this file
    @param timeout: The maximal time duration (in seconds) to wait for
            each step of the login procedure (i.e. the "Are you sure" prompt
            or the password prompt)
    @raise LoginBadClientError: If an unknown client is requested
    @raise: Whatever _remote_login() raises
    @return: A ShellSession object.
    """
    if client == "ssh":
        cmd = ("ssh -o UserKnownHostsFile=/dev/null "
               "-o PreferredAuthentications=password -p %s %s@%s" %
               (port, username, host))
    elif client == "telnet":
        cmd = "telnet -l %s %s %s" % (username, host, port)
    elif client == "nc":
        cmd = "nc %s %s" % (host, port)
    else:
        raise LoginBadClientError(client)

    logging.debug("Login command: '%s'", cmd)
    session = aexpect.ShellSession(cmd, linesep=linesep, prompt=prompt)
    try:
        _remote_login(session, username, password, prompt, timeout)
    except Exception:
        session.close()
        raise
    if log_filename:
        session.set_output_func(log_line)
        session.set_output_params((log_filename,))
    return session


def wait_for_login(client, host, port, username, password, prompt, linesep="\n",
                   log_filename=None, timeout=240, internal_timeout=10):
    """
    Make multiple attempts to log into a remote host (guest) until one succeeds
    or timeout expires.

    @param timeout: Total time duration to wait for a successful login
    @param internal_timeout: The maximal time duration (in seconds) to wait for
            each step of the login procedure (e.g. the "Are you sure" prompt
            or the password prompt)
    @see: remote_login()
    @raise: Whatever remote_login() raises
    @return: A ShellSession object.
    """
    logging.debug("Attempting to log into %s:%s using %s (timeout %ds)",
                  host, port, client, timeout)
    end_time = time.time() + timeout
    while time.time() < end_time:
        try:
            return remote_login(client, host, port, username, password, prompt,
                                linesep, log_filename, internal_timeout)
        except LoginError, e:
            logging.debug(e)
        time.sleep(2)
    # Timeout expired; try one more time but don't catch exceptions
    return remote_login(client, host, port, username, password, prompt,
                        linesep, log_filename, internal_timeout)


def _remote_scp(session, password_list, transfer_timeout=600, login_timeout=20):
    """
    Transfer file(s) to a remote host (guest) using SCP.  Wait for questions
    and provide answers.  If login_timeout expires while waiting for output
    from the child (e.g. a password prompt), fail.  If transfer_timeout expires
    while waiting for the transfer to complete, fail.

    @brief: Transfer files using SCP, given a command line.

    @param session: An Expect or ShellSession instance to operate on
    @param password_list: Password list to send in reply to the password prompt
    @param transfer_timeout: The time duration (in seconds) to wait for the
            transfer to complete.
    @param login_timeout: The maximal time duration (in seconds) to wait for
            each step of the login procedure (i.e. the "Are you sure" prompt or
            the password prompt)
    @raise SCPAuthenticationError: If authentication fails
    @raise SCPTransferTimeoutError: If the transfer fails to complete in time
    @raise SCPTransferFailedError: If the process terminates with a nonzero
            exit code
    @raise SCPError: If some other error occurs
    """
    password_prompt_count = 0
    timeout = login_timeout
    authentication_done = False

    scp_type = len(password_list)

    while True:
        try:
            match, text = session.read_until_last_line_matches(
                [r"[Aa]re you sure", r"[Pp]assword:\s*$", r"lost connection"],
                timeout=timeout, internal_timeout=0.5)
            if match == 0:  # "Are you sure you want to continue connecting"
                logging.debug("Got 'Are you sure...', sending 'yes'")
                session.sendline("yes")
                continue
            elif match == 1:  # "password:"
                if password_prompt_count == 0:
                    logging.debug("Got password prompt, sending '%s'" %
                                   password_list[password_prompt_count])
                    session.sendline(password_list[password_prompt_count])
                    password_prompt_count += 1
                    timeout = transfer_timeout
                    if scp_type == 1:
                        authentication_done = True
                    continue
                elif password_prompt_count == 1 and scp_type == 2:
                    logging.debug("Got password prompt, sending '%s'" %
                                   password_list[password_prompt_count])
                    session.sendline(password_list[password_prompt_count])
                    password_prompt_count += 1
                    timeout = transfer_timeout
                    authentication_done = True
                    continue
                else:
                    raise SCPAuthenticationError("Got password prompt twice",
                                                 text)
            elif match == 2:  # "lost connection"
                raise SCPError("SCP client said 'lost connection'", text)
        except aexpect.ExpectTimeoutError, e:
            if authentication_done:
                raise SCPTransferTimeoutError(e.output)
            else:
                raise SCPAuthenticationTimeoutError(e.output)
        except aexpect.ExpectProcessTerminatedError, e:
            if e.status == 0:
                logging.debug("SCP process terminated with status 0")
                break
            else:
                raise SCPTransferFailedError(e.status, e.output)


def remote_scp(command, password_list, log_filename=None, transfer_timeout=600,
               login_timeout=20):
    """
    Transfer file(s) to a remote host (guest) using SCP.

    @brief: Transfer files using SCP, given a command line.

    @param command: The command to execute
        (e.g. "scp -r foobar root@localhost:/tmp/").
    @param password_list: Password list to send in reply to a password prompt.
    @param log_filename: If specified, log all output to this file
    @param transfer_timeout: The time duration (in seconds) to wait for the
            transfer to complete.
    @param login_timeout: The maximal time duration (in seconds) to wait for
            each step of the login procedure (i.e. the "Are you sure" prompt
            or the password prompt)
    @raise: Whatever _remote_scp() raises
    """
    logging.debug("Trying to SCP with command '%s', timeout %ss",
                  command, transfer_timeout)
    if log_filename:
        output_func = log_line
        output_params = (log_filename,)
    else:
        output_func = None
        output_params = ()
    session = aexpect.Expect(command,
                                    output_func=output_func,
                                    output_params=output_params)
    try:
        _remote_scp(session, password_list, transfer_timeout, login_timeout)
    finally:
        session.close()


def scp_to_remote(host, port, username, password, local_path, remote_path,
                  limit="", log_filename=None, timeout=600):
    """
    Copy files to a remote host (guest) through scp.

    @param host: Hostname or IP address
    @param username: Username (if required)
    @param password: Password (if required)
    @param local_path: Path on the local machine where we are copying from
    @param remote_path: Path on the remote machine where we are copying to
    @param limit: Speed limit of file transfer.
    @param log_filename: If specified, log all output to this file
    @param timeout: The time duration (in seconds) to wait for the transfer
            to complete.
    @raise: Whatever remote_scp() raises
    """
    if (limit):
        limit = "-l %s" % (limit)

    command = ("scp -v -o UserKnownHostsFile=/dev/null "
               "-o PreferredAuthentications=password -r %s "
               "-P %s %s %s@%s:%s" %
               (limit, port, local_path, username, host, remote_path))
    password_list = []
    password_list.append(password)
    return remote_scp(command, password_list, log_filename, timeout)


def scp_from_remote(host, port, username, password, remote_path, local_path,
                    limit="", log_filename=None, timeout=600, ):
    """
    Copy files from a remote host (guest).

    @param host: Hostname or IP address
    @param username: Username (if required)
    @param password: Password (if required)
    @param local_path: Path on the local machine where we are copying from
    @param remote_path: Path on the remote machine where we are copying to
    @param limit: Speed limit of file transfer.
    @param log_filename: If specified, log all output to this file
    @param timeout: The time duration (in seconds) to wait for the transfer
            to complete.
    @raise: Whatever remote_scp() raises
    """
    if (limit):
        limit = "-l %s" % (limit)

    command = ("scp -v -o UserKnownHostsFile=/dev/null "
               "-o PreferredAuthentications=password -r %s "
               "-P %s %s@%s:%s %s" %
               (limit, port, username, host, remote_path, local_path))
    password_list = []
    password_list.append(password)
    remote_scp(command, password_list, log_filename, timeout)


def scp_between_remotes(src, dst, port, s_passwd, d_passwd, s_name, d_name,
                        s_path, d_path, limit="", log_filename=None,
                        timeout=600):
    """
    Copy files from a remote host (guest) to another remote host (guest).

    @param src/dst: Hostname or IP address of src and dst
    @param s_name/d_name: Username (if required)
    @param s_passwd/d_passwd: Password (if required)
    @param s_path/d_path: Path on the remote machine where we are copying
                         from/to
    @param limit: Speed limit of file transfer.
    @param log_filename: If specified, log all output to this file
    @param timeout: The time duration (in seconds) to wait for the transfer
            to complete.

    @return: True on success and False on failure.
    """
    if (limit):
        limit = "-l %s" % (limit)

    command = ("scp -v -o UserKnownHostsFile=/dev/null -o "
               "PreferredAuthentications=password -r %s -P %s"
               " %s@%s:%s %s@%s:%s" %
               (limit, port, s_name, src, s_path, d_name, dst, d_path))
    password_list = []
    password_list.append(s_passwd)
    password_list.append(d_passwd)
    return remote_scp(command, password_list, log_filename, timeout)


def copy_files_to(address, client, username, password, port, local_path,
                  remote_path, limit="", log_filename=None,
                  verbose=False, timeout=600):
    """
    Copy files to a remote host (guest) using the selected client.

    @param client: Type of transfer client
    @param username: Username (if required)
    @param password: Password (if requried)
    @param local_path: Path on the local machine where we are copying from
    @param remote_path: Path on the remote machine where we are copying to
    @param address: Address of remote host(guest)
    @param limit: Speed limit of file transfer.
    @param log_filename: If specified, log all output to this file (SCP only)
    @param verbose: If True, log some stats using logging.debug (RSS only)
    @param timeout: The time duration (in seconds) to wait for the transfer to
            complete.
    @raise: Whatever remote_scp() raises
    """
    if client == "scp":
        scp_to_remote(address, port, username, password, local_path,
                      remote_path, limit, log_filename, timeout)
    elif client == "rss":
        log_func = None
        if verbose:
            log_func = logging.debug
        c = rss_client.FileUploadClient(address, port, log_func)
        c.upload(local_path, remote_path, timeout)
        c.close()


def copy_files_from(address, client, username, password, port, remote_path,
                    local_path, limit="", log_filename=None,
                    verbose=False, timeout=600):
    """
    Copy files from a remote host (guest) using the selected client.

    @param client: Type of transfer client
    @param username: Username (if required)
    @param password: Password (if requried)
    @param remote_path: Path on the remote machine where we are copying from
    @param local_path: Path on the local machine where we are copying to
    @param address: Address of remote host(guest)
    @param limit: Speed limit of file transfer.
    @param log_filename: If specified, log all output to this file (SCP only)
    @param verbose: If True, log some stats using logging.debug (RSS only)
    @param timeout: The time duration (in seconds) to wait for the transfer to
    complete.
    @raise: Whatever remote_scp() raises
    """
    if client == "scp":
        scp_from_remote(address, port, username, password, remote_path,
                        local_path, limit, log_filename, timeout)
    elif client == "rss":
        log_func = None
        if verbose:
            log_func = logging.debug
        c = rss_client.FileDownloadClient(address, port, log_func)
        c.download(remote_path, local_path, timeout)
        c.close()


# The following are utility functions related to ports.

def is_port_free(port, address):
    """
    Return True if the given port is available for use.

    @param port: Port number
    """
    try:
        s = socket.socket()
        #s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        if address == "localhost":
            s.bind(("localhost", port))
            free = True
        else:
            s.connect((address, port))
            free = False
    except socket.error:
        if address == "localhost":
            free = False
        else:
            free = True
    s.close()
    return free


def find_free_port(start_port, end_port, address="localhost"):
    """
    Return a host free port in the range [start_port, end_port].

    @param start_port: First port that will be checked.
    @param end_port: Port immediately after the last one that will be checked.
    """
    for i in range(start_port, end_port):
        if is_port_free(i, address):
            return i
    return None


def find_free_ports(start_port, end_port, count, address="localhost"):
    """
    Return count of host free ports in the range [start_port, end_port].

    @count: Initial number of ports known to be free in the range.
    @param start_port: First port that will be checked.
    @param end_port: Port immediately after the last one that will be checked.
    """
    ports = []
    i = start_port
    while i < end_port and count > 0:
        if is_port_free(i, address):
            ports.append(i)
            count -= 1
        i += 1
    return ports


# An easy way to log lines to files when the logging system can't be used

_open_log_files = {}
_log_file_dir = "/tmp"


def log_line(filename, line):
    """
    Write a line to a file.  '\n' is appended to the line.

    @param filename: Path of file to write to, either absolute or relative to
            the dir set by set_log_file_dir().
    @param line: Line to write.
    """
    global _open_log_files, _log_file_dir
    if filename not in _open_log_files:
        path = get_path(_log_file_dir, filename)
        try:
            os.makedirs(os.path.dirname(path))
        except OSError:
            pass
        _open_log_files[filename] = open(path, "w")
    timestr = time.strftime("%Y-%m-%d %H:%M:%S")
    _open_log_files[filename].write("%s: %s\n" % (timestr, line))
    _open_log_files[filename].flush()


def set_log_file_dir(dir):
    """
    Set the base directory for log files created by log_line().

    @param dir: Directory for log files.
    """
    global _log_file_dir
    _log_file_dir = dir


# The following are miscellaneous utility functions.

def get_path(base_path, user_path):
    """
    Translate a user specified path to a real path.
    If user_path is relative, append it to base_path.
    If user_path is absolute, return it as is.

    @param base_path: The base path of relative user specified paths.
    @param user_path: The user specified path.
    """
    if os.path.isabs(user_path):
        return user_path
    else:
        return os.path.join(base_path, user_path)


def generate_random_string(length):
    """
    Return a random string using alphanumeric characters.

    @length: length of the string that will be generated.
    """
    r = random.SystemRandom()
    str = ""
    chars = string.letters + string.digits
    while length > 0:
        str += r.choice(chars)
        length -= 1
    return str

def generate_random_id():
    """
    Return a random string suitable for use as a qemu id.
    """
    return "id" + generate_random_string(6)


def generate_tmp_file_name(file, ext=None, dir='/tmp/'):
    """
    Returns a temporary file name. The file is not created.
    """
    while True:
        file_name = (file + '-' + time.strftime("%Y%m%d-%H%M%S-") +
                     generate_random_string(4))
        if ext:
            file_name += '.' + ext
        file_name = os.path.join(dir, file_name)
        if not os.path.exists(file_name):
            break

    return file_name


def format_str_for_message(str):
    """
    Format str so that it can be appended to a message.
    If str consists of one line, prefix it with a space.
    If str consists of multiple lines, prefix it with a newline.

    @param str: string that will be formatted.
    """
    lines = str.splitlines()
    num_lines = len(lines)
    str = "\n".join(lines)
    if num_lines == 0:
        return ""
    elif num_lines == 1:
        return " " + str
    else:
        return "\n" + str


def wait_for(func, timeout, first=0.0, step=1.0, text=None):
    """
    If func() evaluates to True before timeout expires, return the
    value of func(). Otherwise return None.

    @brief: Wait until func() evaluates to True.

    @param timeout: Timeout in seconds
    @param first: Time to sleep before first attempt
    @param steps: Time to sleep between attempts in seconds
    @param text: Text to print while waiting, for debug purposes
    """
    start_time = time.time()
    end_time = time.time() + timeout

    time.sleep(first)

    while time.time() < end_time:
        if text:
            logging.debug("%s (%f secs)", text, (time.time() - start_time))

        output = func()
        if output:
            return output

        time.sleep(step)

    return None


def get_hash_from_file(hash_path, dvd_basename):
    """
    Get the a hash from a given DVD image from a hash file
    (Hash files are usually named MD5SUM or SHA1SUM and are located inside the
    download directories of the DVDs)

    @param hash_path: Local path to a hash file.
    @param cd_image: Basename of a CD image
    """
    hash_file = open(hash_path, 'r')
    for line in hash_file.readlines():
        if dvd_basename in line:
            return line.split()[0]


def run_tests(parser, job):
    """
    Runs the sequence of KVM tests based on the list of dictionaries
    generated by the configuration system, handling dependencies.

    @param parser: Config parser object.
    @param job: Autotest job object.

    @return: True, if all tests ran passed, False if any of them failed.
    """
    for i, d in enumerate(parser.get_dicts()):
        logging.info("Test %4d:  %s" % (i + 1, d["shortname"]))

    status_dict = {}
    failed = False

    for dict in parser.get_dicts():
        if dict.get("skip") == "yes":
            continue
        dependencies_satisfied = True
        for dep in dict.get("dep"):
            for test_name in status_dict.keys():
                if not dep in test_name:
                    continue
                # So the only really non-fatal state is WARN,
                # All the others make it not safe to proceed with dependency
                # execution
                if status_dict[test_name] not in ['GOOD', 'WARN']:
                    dependencies_satisfied = False
                    break
        test_iterations = int(dict.get("iterations", 1))
        test_tag = dict.get("shortname")

        if dependencies_satisfied:
            # Setting up profilers during test execution.
            profilers = dict.get("profilers", "").split()
            for profiler in profilers:
                job.profilers.add(profiler)
            # We need only one execution, profiled, hence we're passing
            # the profile_only parameter to job.run_test().
            profile_only = bool(profilers) or None
            current_status = job.run_test_detail(dict.get("vm_type"),
                                                 params=dict,
                                                 tag=test_tag,
                                                 iterations=test_iterations,
                                                 profile_only=profile_only)
            for profiler in profilers:
                job.profilers.delete(profiler)
        else:
            # We will force the test to fail as TestNA during preprocessing
            dict['dependency_failed'] = 'yes'
            current_status = job.run_test_detail(dict.get("vm_type"),
                                                 params=dict,
                                                 tag=test_tag,
                                                 iterations=test_iterations)

        if not current_status:
            failed = True
        status_dict[dict.get("name")] = current_status

    return not failed


def display_attributes(instance):
    """
    Inspects a given class instance attributes and displays them, convenient
    for debugging.
    """
    logging.debug("Attributes set:")
    for member in inspect.getmembers(instance):
        name, value = member
        attribute = getattr(instance, name)
        if not (name.startswith("__") or callable(attribute) or not value):
            logging.debug("    %s: %s", name, value)


def get_full_pci_id(pci_id):
    """
    Get full PCI ID of pci_id.

    @param pci_id: PCI ID of a device.
    """
    cmd = "lspci -D | awk '/%s/ {print $1}'" % pci_id
    status, full_id = commands.getstatusoutput(cmd)
    if status != 0:
        return None
    return full_id


def get_vendor_from_pci_id(pci_id):
    """
    Check out the device vendor ID according to pci_id.

    @param pci_id: PCI ID of a device.
    """
    cmd = "lspci -n | awk '/%s/ {print $3}'" % pci_id
    return re.sub(":", " ", commands.getoutput(cmd))


class Flag(str):
    """
    Class for easy merge cpuflags.
    """
    aliases = {}

    def __new__(cls, flag):
        if flag in Flag.aliases:
            flag = Flag.aliases[flag]
        return str.__new__(cls, flag)

    def __eq__(self, other):
        s = set(self.split("|"))
        o = set(other.split("|"))
        if s & o:
            return True
        else:
            return False

    def __str__(self):
        return self.split("|")[0]

    def __repr__(self):
        return self.split("|")[0]

    def __hash__(self, *args, **kwargs):
        return 0


kvm_map_flags_to_test = {
            Flag('avx')                        :set(['avx']),
            Flag('sse3|pni')                   :set(['sse3']),
            Flag('ssse3')                      :set(['ssse3']),
            Flag('sse4.1|sse4_1|sse4.2|sse4_2'):set(['sse4']),
            Flag('aes')                        :set(['aes','pclmul']),
            Flag('pclmuldq')                   :set(['pclmul']),
            Flag('pclmulqdq')                  :set(['pclmul']),
            Flag('rdrand')                     :set(['rdrand']),
            Flag('sse4a')                      :set(['sse4a']),
            Flag('fma4')                       :set(['fma4']),
            Flag('xop')                        :set(['xop']),
            }


kvm_map_flags_aliases = {
            'sse4.1'              :'sse4_1',
            'sse4.2'              :'sse4_2',
            'pclmulqdq'           :'pclmuldq',
            }


def kvm_flags_to_stresstests(flags):
    """
    Covert [cpu flags] to [tests]

    @param cpuflags: list of cpuflags
    @return: Return tests like string.
    """
    tests = set([])
    for f in flags:
        tests |= kvm_map_flags_to_test[f]
    param = ""
    for f in tests:
        param += ","+f
    return param


def get_cpu_flags():
    """
    Returns a list of the CPU flags
    """
    flags_re = re.compile(r'^flags\s*:(.*)')
    for line in open('/proc/cpuinfo').readlines():
        match = flags_re.match(line)
        if match:
            return match.groups()[0].split()
    return []


def get_cpu_vendor(cpu_flags=[], verbose=True):
    """
    Returns the name of the CPU vendor, either intel, amd or unknown
    """
    if not cpu_flags:
        cpu_flags = get_cpu_flags()

    if 'vmx' in cpu_flags:
        vendor = 'intel'
    elif 'svm' in cpu_flags:
        vendor = 'amd'
    else:
        vendor = 'unknown'

    if verbose:
        logging.debug("Detected CPU vendor as '%s'", vendor)
    return vendor


def get_archive_tarball_name(source_dir, tarball_name, compression):
    '''
    Get the name for a tarball file, based on source, name and compression
    '''
    if tarball_name is None:
        tarball_name = os.path.basename(source_dir)

    if not tarball_name.endswith('.tar'):
        tarball_name = '%s.tar' % tarball_name

    if compression and not tarball_name.endswith('.%s' % compression):
        tarball_name = '%s.%s' % (tarball_name, compression)

    return tarball_name


def archive_as_tarball(source_dir, dest_dir, tarball_name=None,
                       compression='bz2', verbose=True):
    '''
    Saves the given source directory to the given destination as a tarball

    If the name of the archive is omitted, it will be taken from the
    source_dir. If it is an absolute path, dest_dir will be ignored. But,
    if both the destination directory and tarball anem is given, and the
    latter is not an absolute path, they will be combined.

    For archiving directory '/tmp' in '/net/server/backup' as file
    'tmp.tar.bz2', simply use:

    >>> virt_utils.archive_as_tarball('/tmp', '/net/server/backup')

    To save the file it with a different name, say 'host1-tmp.tar.bz2'
    and save it under '/net/server/backup', use:

    >>> virt_utils.archive_as_tarball('/tmp', '/net/server/backup',
                                      'host1-tmp')

    To save with gzip compression instead (resulting in the file
    '/net/server/backup/host1-tmp.tar.gz'), use:

    >>> virt_utils.archive_as_tarball('/tmp', '/net/server/backup',
                                      'host1-tmp', 'gz')
    '''
    tarball_name = get_archive_tarball_name(source_dir,
                                            tarball_name,
                                            compression)
    if not os.path.isabs(tarball_name):
        tarball_path = os.path.join(dest_dir, tarball_name)
    else:
        tarball_path = tarball_name

    if verbose:
        logging.debug('Archiving %s as %s' % (source_dir,
                                              tarball_path))

    os.chdir(os.path.dirname(source_dir))
    tarball = tarfile.TarFile(name=tarball_path, mode='w')
    tarball = tarball.open(name=tarball_path, mode='w:%s' % compression)
    tarball.add(os.path.basename(source_dir))
    tarball.close()


def parallel(targets):
    """
    Run multiple functions in parallel.

    @param targets: A sequence of tuples or functions.  If it's a sequence of
            tuples, each tuple will be interpreted as (target, args, kwargs) or
            (target, args) or (target,) depending on its length.  If it's a
            sequence of functions, the functions will be called without
            arguments.
    @return: A list of the values returned by the functions called.
    """
    threads = []
    for target in targets:
        if isinstance(target, tuple) or isinstance(target, list):
            t = utils.InterruptedThread(*target)
        else:
            t = utils.InterruptedThread(target)
        threads.append(t)
        t.start()
    return [t.join() for t in threads]


class VirtLoggingConfig(logging_config.LoggingConfig):
    """
    Used with the sole purpose of providing convenient logging setup
    for the KVM test auxiliary programs.
    """
    def configure_logging(self, results_dir=None, verbose=False):
        super(VirtLoggingConfig, self).configure_logging(use_console=True,
                                                         verbose=verbose)


class PciAssignable(object):
    """
    Request PCI assignable devices on host. It will check whether to request
    PF (physical Functions) or VF (Virtual Functions).
    """
    def __init__(self, type="vf", driver=None, driver_option=None,
                 names=None, devices_requested=None):
        """
        Initialize parameter 'type' which could be:
        vf: Virtual Functions
        pf: Physical Function (actual hardware)
        mixed:  Both includes VFs and PFs

        If pass through Physical NIC cards, we need to specify which devices
        to be assigned, e.g. 'eth1 eth2'.

        If pass through Virtual Functions, we need to specify how many vfs
        are going to be assigned, e.g. passthrough_count = 8 and max_vfs in
        config file.

        @param type: PCI device type.
        @param driver: Kernel module for the PCI assignable device.
        @param driver_option: Module option to specify the maximum number of
                VFs (eg 'max_vfs=7')
        @param names: Physical NIC cards correspondent network interfaces,
                e.g.'eth1 eth2 ...'
        @param devices_requested: Number of devices being requested.
        """
        self.type = type
        self.driver = driver
        self.driver_option = driver_option
        if names:
            self.name_list = names.split()
        if devices_requested:
            self.devices_requested = int(devices_requested)
        else:
            self.devices_requested = None


    def _get_pf_pci_id(self, name, search_str):
        """
        Get the PF PCI ID according to name.

        @param name: Name of the PCI device.
        @param search_str: Search string to be used on lspci.
        """
        cmd = "ethtool -i %s | awk '/bus-info/ {print $2}'" % name
        s, pci_id = commands.getstatusoutput(cmd)
        if not (s or "Cannot get driver information" in pci_id):
            return pci_id[5:]
        cmd = "lspci | awk '/%s/ {print $1}'" % search_str
        pci_ids = [id for id in commands.getoutput(cmd).splitlines()]
        nic_id = int(re.search('[0-9]+', name).group(0))
        if (len(pci_ids) - 1) < nic_id:
            return None
        return pci_ids[nic_id]


    def _release_dev(self, pci_id):
        """
        Release a single PCI device.

        @param pci_id: PCI ID of a given PCI device.
        """
        base_dir = "/sys/bus/pci"
        full_id = get_full_pci_id(pci_id)
        vendor_id = get_vendor_from_pci_id(pci_id)
        drv_path = os.path.join(base_dir, "devices/%s/driver" % full_id)
        if 'pci-stub' in os.readlink(drv_path):
            cmd = "echo '%s' > %s/new_id" % (vendor_id, drv_path)
            if os.system(cmd):
                return False

            stub_path = os.path.join(base_dir, "drivers/pci-stub")
            cmd = "echo '%s' > %s/unbind" % (full_id, stub_path)
            if os.system(cmd):
                return False

            driver = self.dev_drivers[pci_id]
            cmd = "echo '%s' > %s/bind" % (full_id, driver)
            if os.system(cmd):
                return False

        return True


    def get_vf_devs(self):
        """
        Catch all VFs PCI IDs.

        @return: List with all PCI IDs for the Virtual Functions avaliable
        """
        if not self.sr_iov_setup():
            return []

        cmd = "lspci | awk '/Virtual Function/ {print $1}'"
        return commands.getoutput(cmd).split()


    def get_pf_devs(self):
        """
        Catch all PFs PCI IDs.

        @return: List with all PCI IDs for the physical hardware requested
        """
        pf_ids = []
        for name in self.name_list:
            pf_id = self._get_pf_pci_id(name, "Ethernet")
            if not pf_id:
                continue
            pf_ids.append(pf_id)
        return pf_ids


    def get_devs(self, count):
        """
        Check out all devices' PCI IDs according to their name.

        @param count: count number of PCI devices needed for pass through
        @return: a list of all devices' PCI IDs
        """
        if self.type == "vf":
            vf_ids = self.get_vf_devs()
        elif self.type == "pf":
            vf_ids = self.get_pf_devs()
        elif self.type == "mixed":
            vf_ids = self.get_vf_devs()
            vf_ids.extend(self.get_pf_devs())
        return vf_ids[0:count]


    def get_vfs_count(self):
        """
        Get VFs count number according to lspci.
        """
        # FIXME: Need to think out a method of identify which
        # 'virtual function' belongs to which physical card considering
        # that if the host has more than one 82576 card. PCI_ID?
        cmd = "lspci | grep 'Virtual Function' | wc -l"
        return int(commands.getoutput(cmd))


    def check_vfs_count(self):
        """
        Check VFs count number according to the parameter driver_options.
        """
        # Network card 82576 has two network interfaces and each can be
        # virtualized up to 7 virtual functions, therefore we multiply
        # two for the value of driver_option 'max_vfs'.
        expected_count = int((re.findall("(\d)", self.driver_option)[0])) * 2
        return (self.get_vfs_count == expected_count)


    def is_binded_to_stub(self, full_id):
        """
        Verify whether the device with full_id is already binded to pci-stub.

        @param full_id: Full ID for the given PCI device
        """
        base_dir = "/sys/bus/pci"
        stub_path = os.path.join(base_dir, "drivers/pci-stub")
        if os.path.exists(os.path.join(stub_path, full_id)):
            return True
        return False


    def sr_iov_setup(self):
        """
        Ensure the PCI device is working in sr_iov mode.

        Check if the PCI hardware device drive is loaded with the appropriate,
        parameters (number of VFs), and if it's not, perform setup.

        @return: True, if the setup was completed successfuly, False otherwise.
        """
        re_probe = False
        s, o = commands.getstatusoutput('lsmod | grep %s' % self.driver)
        if s:
            re_probe = True
        elif not self.check_vfs_count():
            os.system("modprobe -r %s" % self.driver)
            re_probe = True
        else:
            return True

        # Re-probe driver with proper number of VFs
        if re_probe:
            cmd = "modprobe %s %s" % (self.driver, self.driver_option)
            logging.info("Loading the driver '%s' with option '%s'",
                         self.driver, self.driver_option)
            s, o = commands.getstatusoutput(cmd)
            if s:
                return False
            return True


    def request_devs(self):
        """
        Implement setup process: unbind the PCI device and then bind it
        to the pci-stub driver.

        @return: a list of successfully requested devices' PCI IDs.
        """
        base_dir = "/sys/bus/pci"
        stub_path = os.path.join(base_dir, "drivers/pci-stub")

        self.pci_ids = self.get_devs(self.devices_requested)
        logging.debug("The following pci_ids were found: %s", self.pci_ids)
        requested_pci_ids = []
        self.dev_drivers = {}

        # Setup all devices specified for assignment to guest
        for pci_id in self.pci_ids:
            full_id = get_full_pci_id(pci_id)
            if not full_id:
                continue
            drv_path = os.path.join(base_dir, "devices/%s/driver" % full_id)
            dev_prev_driver = os.path.realpath(os.path.join(drv_path,
                                               os.readlink(drv_path)))
            self.dev_drivers[pci_id] = dev_prev_driver

            # Judge whether the device driver has been binded to stub
            if not self.is_binded_to_stub(full_id):
                logging.debug("Binding device %s to stub", full_id)
                vendor_id = get_vendor_from_pci_id(pci_id)
                stub_new_id = os.path.join(stub_path, 'new_id')
                unbind_dev = os.path.join(drv_path, 'unbind')
                stub_bind = os.path.join(stub_path, 'bind')

                info_write_to_files = [(vendor_id, stub_new_id),
                                       (full_id, unbind_dev),
                                       (full_id, stub_bind)]

                for content, file in info_write_to_files:
                    try:
                        utils.open_write_close(file, content)
                    except IOError:
                        logging.debug("Failed to write %s to file %s", content,
                                      file)
                        continue

                if not self.is_binded_to_stub(full_id):
                    logging.error("Binding device %s to stub failed", pci_id)
                    continue
            else:
                logging.debug("Device %s already binded to stub", pci_id)
            requested_pci_ids.append(pci_id)
        self.pci_ids = requested_pci_ids
        return self.pci_ids


    def release_devs(self):
        """
        Release all PCI devices currently assigned to VMs back to the
        virtualization host.
        """
        try:
            for pci_id in self.dev_drivers:
                if not self._release_dev(pci_id):
                    logging.error("Failed to release device %s to host", pci_id)
                else:
                    logging.info("Released device %s successfully", pci_id)
        except Exception:
            return


class KojiDirIndexParser(HTMLParser.HTMLParser):
    '''
    Parser for HTML directory index pages, specialized to look for RPM links
    '''
    def __init__(self):
        '''
        Initializes a new KojiDirListParser instance
        '''
        HTMLParser.HTMLParser.__init__(self)
        self.package_file_names = []


    def handle_starttag(self, tag, attrs):
        '''
        Handle tags during the parsing

        This just looks for links ('a' tags) for files ending in .rpm
        '''
        if tag == 'a':
            for k, v in attrs:
                if k == 'href' and v.endswith('.rpm'):
                    self.package_file_names.append(v)


class RPMFileNameInfo:
    '''
    Simple parser for RPM based on information present on the filename itself
    '''
    def __init__(self, filename):
        '''
        Initializes a new RpmInfo instance based on a filename
        '''
        self.filename = filename


    def get_filename_without_suffix(self):
        '''
        Returns the filename without the default RPM suffix
        '''
        assert self.filename.endswith('.rpm')
        return self.filename[0:-4]


    def get_filename_without_arch(self):
        '''
        Returns the filename without the architecture

        This also excludes the RPM suffix, that is, removes the leading arch
        and RPM suffix.
        '''
        wo_suffix = self.get_filename_without_suffix()
        arch_sep = wo_suffix.rfind('.')
        return wo_suffix[:arch_sep]


    def get_arch(self):
        '''
        Returns just the architecture as present on the RPM filename
        '''
        wo_suffix = self.get_filename_without_suffix()
        arch_sep = wo_suffix.rfind('.')
        return wo_suffix[arch_sep+1:]


    def get_nvr_info(self):
        '''
        Returns a dictionary with the name, version and release components

        If koji is not installed, this returns None
        '''
        if not KOJI_INSTALLED:
            return None
        return koji.util.koji.parse_NVR(self.get_filename_without_arch())


class KojiClient(object):
    """
    Stablishes a connection with the build system, either koji or brew.

    This class provides convenience methods to retrieve information on packages
    and the packages themselves hosted on the build system. Packages should be
    specified in the KojiPgkSpec syntax.
    """

    CMD_LOOKUP_ORDER = ['/usr/bin/brew', '/usr/bin/koji' ]

    CONFIG_MAP = {'/usr/bin/brew': '/etc/brewkoji.conf',
                  '/usr/bin/koji': '/etc/koji.conf'}


    def __init__(self, cmd=None):
        """
        Verifies whether the system has koji or brew installed, then loads
        the configuration file that will be used to download the files.

        @type cmd: string
        @param cmd: Optional command name, either 'brew' or 'koji'. If not
                set, get_default_command() is used and to look for
                one of them.
        @raise: ValueError
        """
        if not KOJI_INSTALLED:
            raise ValueError('No koji/brew installed on the machine')

        # Instance variables used by many methods
        self.command = None
        self.config = None
        self.config_options = {}
        self.session = None

        # Set koji command or get default
        if cmd is None:
            self.command = self.get_default_command()
        else:
            self.command = cmd

        # Check koji command
        if not self.is_command_valid():
            raise ValueError('Koji command "%s" is not valid' % self.command)

        # Assuming command is valid, set configuration file and read it
        self.config = self.CONFIG_MAP[self.command]
        self.read_config()

        # Setup koji session
        server_url = self.config_options['server']
        session_options = self.get_session_options()
        self.session = koji.ClientSession(server_url,
                                          session_options)


    def read_config(self, check_is_valid=True):
        '''
        Reads options from the Koji configuration file

        By default it checks if the koji configuration is valid

        @type check_valid: boolean
        @param check_valid: whether to include a check on the configuration
        @raises: ValueError
        @returns: None
        '''
        if check_is_valid:
            if not self.is_config_valid():
                raise ValueError('Koji config "%s" is not valid' % self.config)

        config = ConfigParser.ConfigParser()
        config.read(self.config)

        basename = os.path.basename(self.command)
        for name, value in config.items(basename):
            self.config_options[name] = value


    def get_session_options(self):
        '''
        Filter only options necessary for setting up a cobbler client session

        @returns: only the options used for session setup
        '''
        session_options = {}
        for name, value in self.config_options.items():
            if name in ('user', 'password', 'debug_xmlrpc', 'debug'):
                session_options[name] = value
        return session_options


    def is_command_valid(self):
        '''
        Checks if the currently set koji command is valid

        @returns: True or False
        '''
        koji_command_ok = True

        if not os.path.isfile(self.command):
            logging.error('Koji command "%s" is not a regular file',
                          self.command)
            koji_command_ok = False

        if not os.access(self.command, os.X_OK):
            logging.warn('Koji command "%s" is not executable: this is '
                         'not fatal but indicates an unexpected situation',
                         self.command)

        if not self.command in self.CONFIG_MAP.keys():
            logging.error('Koji command "%s" does not have a configuration '
                          'file associated to it', self.command)
            koji_command_ok = False

        return koji_command_ok


    def is_config_valid(self):
        '''
        Checks if the currently set koji configuration is valid

        @returns: True or False
        '''
        koji_config_ok = True

        if not os.path.isfile(self.config):
            logging.error('Koji config "%s" is not a regular file', self.config)
            koji_config_ok = False

        if not os.access(self.config, os.R_OK):
            logging.error('Koji config "%s" is not readable', self.config)
            koji_config_ok = False

        config = ConfigParser.ConfigParser()
        config.read(self.config)
        basename = os.path.basename(self.command)
        if not config.has_section(basename):
            logging.error('Koji configuration file "%s" does not have a '
                          'section "%s", named after the base name of the '
                          'currently set koji command "%s"', self.config,
                           basename, self.command)
            koji_config_ok = False

        return koji_config_ok


    def get_default_command(self):
        '''
        Looks up for koji or brew "binaries" on the system

        Systems with plain koji usually don't have a brew cmd, while systems
        with koji, have *both* koji and brew utilities. So we look for brew
        first, and if found, we consider that the system is configured for
        brew. If not, we consider this is a system with plain koji.

        @returns: either koji or brew command line executable path, or None
        '''
        koji_command = None
        for command in self.CMD_LOOKUP_ORDER:
            if os.path.isfile(command):
                koji_command = command
                break
            else:
                koji_command_basename = os.path.basename(command)
                try:
                    koji_command = os_dep.command(koji_command_basename)
                    break
                except ValueError:
                    pass
        return koji_command


    def get_pkg_info(self, pkg):
        '''
        Returns information from Koji on the package

        @type pkg: KojiPkgSpec
        @param pkg: information about the package, as a KojiPkgSpec instance

        @returns: information from Koji about the specified package
        '''
        info = {}
        if pkg.build is not None:
            info = self.session.getBuild(int(pkg.build))
        elif pkg.tag is not None and pkg.package is not None:
            builds = self.session.listTagged(pkg.tag,
                                             latest=True,
                                             inherit=True,
                                             package=pkg.package)
            if builds:
                info = builds[0]
        return info


    def is_pkg_valid(self, pkg):
        '''
        Checks if this package is altogether valid on Koji

        This verifies if the build or tag specified in the package
        specification actually exist on the Koji server

        @returns: True or False
        '''
        valid = True
        if pkg.build:
            if not self.is_pkg_spec_build_valid(pkg):
                valid = False
        elif pkg.tag:
            if not self.is_pkg_spec_tag_valid(pkg):
                valid = False
        else:
            valid = False
        return valid


    def is_pkg_spec_build_valid(self, pkg):
        '''
        Checks if build is valid on Koji

        @param pkg: a Pkg instance
        '''
        if pkg.build is not None:
            info = self.session.getBuild(int(pkg.build))
            if info:
                return True
        return False


    def is_pkg_spec_tag_valid(self, pkg):
        '''
        Checks if tag is valid on Koji

        @type pkg: KojiPkgSpec
        @param pkg: a package specification
        '''
        if pkg.tag is not None:
            tag = self.session.getTag(pkg.tag)
            if tag:
                return True
        return False


    def get_pkg_rpm_info(self, pkg, arch=None):
        '''
        Returns a list of infomation on the RPM packages found on koji

        @type pkg: KojiPkgSpec
        @param pkg: a package specification
        @type arch: string
        @param arch: packages built for this architecture, but also including
                architecture independent (noarch) packages
        '''
        if arch is None:
            arch = utils.get_arch()
        rpms = []
        info = self.get_pkg_info(pkg)
        if info:
            rpms = self.session.listRPMs(buildID=info['id'],
                                         arches=[arch, 'noarch'])
            if pkg.subpackages:
                rpms = [d for d in rpms if d['name'] in pkg.subpackages]
        return rpms


    def get_pkg_rpm_names(self, pkg, arch=None):
        '''
        Gets the names for the RPM packages specified in pkg

        @type pkg: KojiPkgSpec
        @param pkg: a package specification
        @type arch: string
        @param arch: packages built for this architecture, but also including
                architecture independent (noarch) packages
        '''
        if arch is None:
            arch = utils.get_arch()
        rpms = self.get_pkg_rpm_info(pkg, arch)
        return [rpm['name'] for rpm in rpms]


    def get_pkg_rpm_file_names(self, pkg, arch=None):
        '''
        Gets the file names for the RPM packages specified in pkg

        @type pkg: KojiPkgSpec
        @param pkg: a package specification
        @type arch: string
        @param arch: packages built for this architecture, but also including
                architecture independent (noarch) packages
        '''
        if arch is None:
            arch = utils.get_arch()
        rpm_names = []
        rpms = self.get_pkg_rpm_info(pkg, arch)
        for rpm in rpms:
            arch_rpm_name = koji.pathinfo.rpm(rpm)
            rpm_name = os.path.basename(arch_rpm_name)
            rpm_names.append(rpm_name)
        return rpm_names


    def get_pkg_base_url(self):
        '''
        Gets the base url for packages in Koji
        '''
        if self.config_options.has_key('pkgurl'):
            return self.config_options['pkgurl']
        else:
            return "%s/%s" % (self.config_options['topurl'],
                              'packages')


    def get_scratch_base_url(self):
        '''
        Gets the base url for scratch builds in Koji
        '''
        one_level_up = os.path.dirname(self.get_pkg_base_url())
        return "%s/%s" % (one_level_up, 'scratch')


    def get_pkg_urls(self, pkg, arch=None):
        '''
        Gets the urls for the packages specified in pkg

        @type pkg: KojiPkgSpec
        @param pkg: a package specification
        @type arch: string
        @param arch: packages built for this architecture, but also including
                architecture independent (noarch) packages
        '''
        info = self.get_pkg_info(pkg)
        rpms = self.get_pkg_rpm_info(pkg, arch)
        rpm_urls = []
        base_url = self.get_pkg_base_url()

        for rpm in rpms:
            rpm_name = koji.pathinfo.rpm(rpm)
            url = ("%s/%s/%s/%s/%s" % (base_url,
                                       info['package_name'],
                                       info['version'], info['release'],
                                       rpm_name))
            rpm_urls.append(url)
        return rpm_urls


    def get_pkgs(self, pkg, dst_dir, arch=None):
        '''
        Download the packages

        @type pkg: KojiPkgSpec
        @param pkg: a package specification
        @type dst_dir: string
        @param dst_dir: the destination directory, where the downloaded
                packages will be saved on
        @type arch: string
        @param arch: packages built for this architecture, but also including
                architecture independent (noarch) packages
        '''
        rpm_urls = self.get_pkg_urls(pkg, arch)
        for url in rpm_urls:
            utils.get_file(url,
                           os.path.join(dst_dir, os.path.basename(url)))


    def get_scratch_pkg_urls(self, pkg, arch=None):
        '''
        Gets the urls for the scratch packages specified in pkg

        @type pkg: KojiScratchPkgSpec
        @param pkg: a scratch package specification
        @type arch: string
        @param arch: packages built for this architecture, but also including
                architecture independent (noarch) packages
        '''
        rpm_urls = []

        if arch is None:
            arch = utils.get_arch()
        arches = [arch, 'noarch']

        index_url = "%s/%s/task_%s" % (self.get_scratch_base_url(),
                                       pkg.user,
                                       pkg.task)
        index_parser = KojiDirIndexParser()
        index_parser.feed(urllib.urlopen(index_url).read())

        if pkg.subpackages:
            for p in pkg.subpackages:
                for pfn in index_parser.package_file_names:
                    r = RPMFileNameInfo(pfn)
                    info = r.get_nvr_info()
                    if (p == info['name'] and
                        r.get_arch() in arches):
                        rpm_urls.append("%s/%s" % (index_url, pfn))
        else:
            for pfn in index_parser.package_file_names:
                if (RPMFileNameInfo(pfn).get_arch() in arches):
                    rpm_urls.append("%s/%s" % (index_url, pfn))

        return rpm_urls


    def get_scratch_pkgs(self, pkg, dst_dir, arch=None):
        '''
        Download the packages from a scratch build

        @type pkg: KojiScratchPkgSpec
        @param pkg: a scratch package specification
        @type dst_dir: string
        @param dst_dir: the destination directory, where the downloaded
                packages will be saved on
        @type arch: string
        @param arch: packages built for this architecture, but also including
                architecture independent (noarch) packages
        '''
        rpm_urls = self.get_scratch_pkg_urls(pkg, arch)
        for url in rpm_urls:
            utils.get_file(url,
                           os.path.join(dst_dir, os.path.basename(url)))


DEFAULT_KOJI_TAG = None
def set_default_koji_tag(tag):
    '''
    Sets the default tag that will be used
    '''
    global DEFAULT_KOJI_TAG
    DEFAULT_KOJI_TAG = tag


def get_default_koji_tag():
    return DEFAULT_KOJI_TAG


class KojiPkgSpec(object):
    '''
    A package specification syntax parser for Koji

    This holds information on either tag or build, and packages to be fetched
    from koji and possibly installed (features external do this class).

    New objects can be created either by providing information in the textual
    format or by using the actual parameters for tag, build, package and sub-
    packages. The textual format is useful for command line interfaces and
    configuration files, while using parameters is better for using this in
    a programatic fashion.

    The following sets of examples are interchangeable. Specifying all packages
    part of build number 1000:

        >>> from kvm_utils import KojiPkgSpec
        >>> pkg = KojiPkgSpec('1000')

        >>> pkg = KojiPkgSpec(build=1000)

    Specifying only a subset of packages of build number 1000:

        >>> pkg = KojiPkgSpec('1000:kernel,kernel-devel')

        >>> pkg = KojiPkgSpec(build=1000,
                              subpackages=['kernel', 'kernel-devel'])

    Specifying the latest build for the 'kernel' package tagged with 'dist-f14':

        >>> pkg = KojiPkgSpec('dist-f14:kernel')

        >>> pkg = KojiPkgSpec(tag='dist-f14', package='kernel')

    Specifying the 'kernel' package using the default tag:

        >>> kvm_utils.set_default_koji_tag('dist-f14')
        >>> pkg = KojiPkgSpec('kernel')

        >>> pkg = KojiPkgSpec(package='kernel')

    Specifying the 'kernel' package using the default tag:

        >>> kvm_utils.set_default_koji_tag('dist-f14')
        >>> pkg = KojiPkgSpec('kernel')

        >>> pkg = KojiPkgSpec(package='kernel')

    If you do not specify a default tag, and give a package name without an
    explicit tag, your package specification is considered invalid:

        >>> print kvm_utils.get_default_koji_tag()
        None
        >>> print kvm_utils.KojiPkgSpec('kernel').is_valid()
        False

        >>> print kvm_utils.KojiPkgSpec(package='kernel').is_valid()
        False
    '''

    SEP = ':'

    def __init__(self, text='', tag=None, build=None,
                 package=None, subpackages=[]):
        '''
        Instantiates a new KojiPkgSpec object

        @type text: string
        @param text: a textual representation of a package on Koji that
                will be parsed
        @type tag: string
        @param tag: a koji tag, example: Fedora-14-RELEASE
                (see U{http://fedoraproject.org/wiki/Koji#Tags_and_Targets})
        @type build: number
        @param build: a koji build, example: 1001
                (see U{http://fedoraproject.org/wiki/Koji#Koji_Architecture})
        @type package: string
        @param package: a koji package, example: python
                (see U{http://fedoraproject.org/wiki/Koji#Koji_Architecture})
        @type subpackages: list of strings
        @param subpackages: a list of package names, usually a subset of
                the RPM packages generated by a given build
        '''

        # Set to None to indicate 'not set' (and be able to use 'is')
        self.tag = None
        self.build = None
        self.package = None
        self.subpackages = []

        self.default_tag = None

        # Textual representation takes precedence (most common use case)
        if text:
            self.parse(text)
        else:
            self.tag = tag
            self.build = build
            self.package = package
            self.subpackages = subpackages

        # Set the default tag, if set, as a fallback
        if not self.build and not self.tag:
            default_tag = get_default_koji_tag()
            if default_tag is not None:
                self.tag = default_tag


    def parse(self, text):
        '''
        Parses a textual representation of a package specification

        @type text: string
        @param text: textual representation of a package in koji
        '''
        parts = text.count(self.SEP) + 1
        if parts == 1:
            if text.isdigit():
                self.build = text
            else:
                self.package = text
        elif parts == 2:
            part1, part2 = text.split(self.SEP)
            if part1.isdigit():
                self.build = part1
                self.subpackages = part2.split(',')
            else:
                self.tag = part1
                self.package = part2
        elif parts >= 3:
            # Instead of erroring on more arguments, we simply ignore them
            # This makes the parser suitable for future syntax additions, such
            # as specifying the package architecture
            part1, part2, part3 = text.split(self.SEP)[0:3]
            self.tag = part1
            self.package = part2
            self.subpackages = part3.split(',')


    def _is_invalid_neither_tag_or_build(self):
        '''
        Checks if this package is invalid due to not having either a valid
        tag or build set, that is, both are empty.

        @returns: True if this is invalid and False if it's valid
        '''
        return (self.tag is None and self.build is None)


    def _is_invalid_package_but_no_tag(self):
        '''
        Checks if this package is invalid due to having a package name set
        but tag or build set, that is, both are empty.

        @returns: True if this is invalid and False if it's valid
        '''
        return (self.package and not self.tag)


    def _is_invalid_subpackages_but_no_main_package(self):
        '''
        Checks if this package is invalid due to having a tag set (this is Ok)
        but specifying subpackage names without specifying the main package
        name.

        Specifying subpackages without a main package name is only valid when
        a build is used instead of a tag.

        @returns: True if this is invalid and False if it's valid
        '''
        return (self.tag and self.subpackages and not self.package)


    def is_valid(self):
        '''
        Checks if this package specification is valid.

        Being valid means that it has enough and not conflicting information.
        It does not validate that the packages specified actually existe on
        the Koji server.

        @returns: True or False
        '''
        if self._is_invalid_neither_tag_or_build():
            return False
        elif self._is_invalid_package_but_no_tag():
            return False
        elif self._is_invalid_subpackages_but_no_main_package():
            return False

        return True


    def describe_invalid(self):
        '''
        Describes why this is not valid, in a human friendly way
        '''
        if self._is_invalid_neither_tag_or_build():
            return 'neither a tag or build are set, and of them should be set'
        elif self._is_invalid_package_but_no_tag():
            return 'package name specified but no tag is set'
        elif self._is_invalid_subpackages_but_no_main_package():
            return 'subpackages specified but no main package is set'

        return 'unkwown reason, seems to be valid'


    def describe(self):
        '''
        Describe this package specification, in a human friendly way

        @returns: package specification description
        '''
        if self.is_valid():
            description = ''
            if not self.subpackages:
                description += 'all subpackages from %s ' % self.package
            else:
                description += ('only subpackage(s) %s from package %s ' %
                                (', '.join(self.subpackages), self.package))

            if self.build:
                description += 'from build %s' % self.build
            elif self.tag:
                description += 'tagged with %s' % self.tag
            else:
                raise ValueError, 'neither build or tag is set'

            return description
        else:
            return ('Invalid package specification: %s' %
                    self.describe_invalid())


    def to_text(self):
        '''
        Return the textual representation of this package spec

        The output should be consumable by parse() and produce the same
        package specification.

        We find that it's acceptable to put the currently set default tag
        as the package explicit tag in the textual definition for completeness.

        @returns: package specification in a textual representation
        '''
        default_tag = get_default_koji_tag()

        if self.build:
            if self.subpackages:
                return "%s:%s" % (self.build, ",".join(self.subpackages))
            else:
                return "%s" % self.build

        elif self.tag:
            if self.subpackages:
                return "%s:%s:%s" % (self.tag, self.package,
                                     ",".join(self.subpackages))
            else:
                return "%s:%s" % (self.tag, self.package)

        elif default_tag is not None:
            # neither build or tag is set, try default_tag as a fallback
            if self.subpackages:
                return "%s:%s:%s" % (default_tag, self.package,
                                     ",".join(self.subpackages))
            else:
                return "%s:%s" % (default_tag, self.package)
        else:
            raise ValueError, 'neither build or tag is set'


    def __repr__(self):
        return ("<KojiPkgSpec tag=%s build=%s pkg=%s subpkgs=%s>" %
                (self.tag, self.build, self.package,
                 ", ".join(self.subpackages)))


class KojiScratchPkgSpec(object):
    '''
    A package specification syntax parser for Koji scratch builds

    This holds information on user, task and subpackages to be fetched
    from koji and possibly installed (features external do this class).

    New objects can be created either by providing information in the textual
    format or by using the actual parameters for user, task and subpackages.
    The textual format is useful for command line interfaces and configuration
    files, while using parameters is better for using this in a programatic
    fashion.

    This package definition has a special behaviour: if no subpackages are
    specified, all packages of the chosen architecture (plus noarch packages)
    will match.

    The following sets of examples are interchangeable. Specifying all packages
    from a scratch build (whose task id is 1000) sent by user jdoe:

        >>> from kvm_utils import KojiScratchPkgSpec
        >>> pkg = KojiScratchPkgSpec('jdoe:1000')

        >>> pkg = KojiScratchPkgSpec(user=jdoe, task=1000)

    Specifying some packages from a scratch build whose task id is 1000, sent
    by user jdoe:

        >>> pkg = KojiScratchPkgSpec('jdoe:1000:kernel,kernel-devel')

        >>> pkg = KojiScratchPkgSpec(user=jdoe, task=1000,
                                     subpackages=['kernel', 'kernel-devel'])
    '''

    SEP = ':'

    def __init__(self, text='', user=None, task=None, subpackages=[]):
        '''
        Instantiates a new KojiScratchPkgSpec object

        @type text: string
        @param text: a textual representation of a scratch build on Koji that
                will be parsed
        @type task: number
        @param task: a koji task id, example: 1001
        @type subpackages: list of strings
        @param subpackages: a list of package names, usually a subset of
                the RPM packages generated by a given build
        '''
        # Set to None to indicate 'not set' (and be able to use 'is')
        self.user = None
        self.task = None
        self.subpackages = []

        # Textual representation takes precedence (most common use case)
        if text:
            self.parse(text)
        else:
            self.user = user
            self.task = task
            self.subpackages = subpackages


    def parse(self, text):
        '''
        Parses a textual representation of a package specification

        @type text: string
        @param text: textual representation of a package in koji
        '''
        parts = text.count(self.SEP) + 1
        if parts == 1:
            raise ValueError('KojiScratchPkgSpec requires a user and task id')
        elif parts == 2:
            self.user, self.task = text.split(self.SEP)
        elif parts >= 3:
            # Instead of erroring on more arguments, we simply ignore them
            # This makes the parser suitable for future syntax additions, such
            # as specifying the package architecture
            part1, part2, part3 = text.split(self.SEP)[0:3]
            self.user = part1
            self.task = part2
            self.subpackages = part3.split(',')


    def __repr__(self):
        return ("<KojiScratchPkgSpec user=%s task=%s subpkgs=%s>" %
                (self.user, self.task, ", ".join(self.subpackages)))


def umount(src, mount_point, type):
    """
    Umount the src mounted in mount_point.

    @src: mount source
    @mount_point: mount point
    @type: file system type
    """

    mount_string = "%s %s %s" % (src, mount_point, type)
    if mount_string in file("/etc/mtab").read():
        umount_cmd = "umount %s" % mount_point
        try:
            utils.system(umount_cmd)
            return True
        except error.CmdError:
            return False
    else:
        logging.debug("%s is not mounted under %s", src, mount_point)
        return True


def mount(src, mount_point, type, perm="rw"):
    """
    Mount the src into mount_point of the host.

    @src: mount source
    @mount_point: mount point
    @type: file system type
    @perm: mount premission
    """
    umount(src, mount_point, type)
    mount_string = "%s %s %s %s" % (src, mount_point, type, perm)

    if mount_string in file("/etc/mtab").read():
        logging.debug("%s is already mounted in %s with %s",
                      src, mount_point, perm)
        return True

    mount_cmd = "mount -t %s %s %s -o %s" % (type, src, mount_point, perm)
    try:
        utils.system(mount_cmd)
    except error.CmdError:
        return False

    logging.debug("Verify the mount through /etc/mtab")
    if mount_string in file("/etc/mtab").read():
        logging.debug("%s is successfully mounted", src)
        return True
    else:
        logging.error("Can't find mounted NFS share - /etc/mtab contents \n%s",
                      file("/etc/mtab").read())
        return False


class GitRepoParamHelper(git.GitRepoHelper):
    '''
    Helps to deal with git repos specified in cartersian config files

    This class attempts to make it simple to manage a git repo, by using a
    naming standard that follows this basic syntax:

    <prefix>_name_<suffix>

    <prefix> is always 'git_repo' and <suffix> sets options for this git repo.
    Example for repo named foo:

    git_repo_foo_uri = git://git.foo.org/foo.git
    git_repo_foo_base_uri = /home/user/code/foo
    git_repo_foo_branch = master
    git_repo_foo_lbranch = master
    git_repo_foo_commit = bb5fb8e678aabe286e74c4f2993dc2a9e550b627
    '''
    def __init__(self, params, name, destination_dir):
        '''
        Instantiates a new GitRepoParamHelper
        '''
        self.params = params
        self.name = name
        self.destination_dir = destination_dir
        self._parse_params()


    def _parse_params(self):
        '''
        Parses the params items for entries related to this repo

        This method currently does everything that the parent class __init__()
        method does, that is, sets all instance variables needed by other
        methods. That means it's not strictly necessary to call parent's
        __init__().
        '''
        config_prefix = 'git_repo_%s' % self.name
        logging.debug('Parsing parameters for git repo %s, configuration '
                      'prefix is %s' % (self.name, config_prefix))

        self.base_uri = self.params.get('%s_base_uri' % config_prefix)
        if self.base_uri is None:
            logging.debug('Git repo %s base uri is not set' % self.name)
        else:
            logging.debug('Git repo %s base uri: %s' % (self.name,
                                                        self.base_uri))

        self.uri = self.params.get('%s_uri' % config_prefix)
        logging.debug('Git repo %s uri: %s' % (self.name, self.uri))

        self.branch = self.params.get('%s_branch' % config_prefix, 'master')
        logging.debug('Git repo %s branch: %s' % (self.name, self.branch))

        self.lbranch = self.params.get('%s_lbranch' % config_prefix)
        if self.lbranch is None:
            self.lbranch = self.branch
        logging.debug('Git repo %s lbranch: %s' % (self.name, self.lbranch))

        self.commit = self.params.get('%s_commit' % config_prefix)
        if self.commit is None:
            logging.debug('Git repo %s commit is not set' % self.name)
        else:
            logging.debug('Git repo %s commit: %s' % (self.name, self.commit))

        self.cmd = os_dep.command('git')


class LocalSourceDirHelper(object):
    '''
    Helper class to deal with source code sitting somewhere in the filesystem
    '''
    def __init__(self, source_dir, destination_dir):
        '''
        @param source_dir:
        @param destination_dir:
        @return: new LocalSourceDirHelper instance
        '''
        self.source = source_dir
        self.destination = destination_dir


    def execute(self):
        '''
        Copies the source directory to the destination directory
        '''
        if os.path.isdir(self.destination):
            shutil.rmtree(self.destination)

        if os.path.isdir(self.source):
            shutil.copytree(self.source, self.destination)


class LocalSourceDirParamHelper(LocalSourceDirHelper):
    '''
    Helps to deal with source dirs specified in cartersian config files

    This class attempts to make it simple to manage a source dir, by using a
    naming standard that follows this basic syntax:

    <prefix>_name_<suffix>

    <prefix> is always 'local_src' and <suffix> sets options for this source
    dir.  Example for source dir named foo:

    local_src_foo_path = /home/user/foo
    '''
    def __init__(self, params, name, destination_dir):
        '''
        Instantiate a new LocalSourceDirParamHelper
        '''
        self.params = params
        self.name = name
        self.destination_dir = destination_dir
        self._parse_params()


    def _parse_params(self):
        '''
        Parses the params items for entries related to source dir
        '''
        config_prefix = 'local_src_%s' % self.name
        logging.debug('Parsing parameters for local source %s, configuration '
                      'prefix is %s' % (self.name, config_prefix))

        self.path = self.params.get('%s_path' % config_prefix)
        logging.debug('Local source directory %s path: %s' % (self.name,
                                                              self.path))
        self.source = self.path
        self.destination = self.destination_dir


class LocalTarHelper(object):
    '''
    Helper class to deal with source code in a local tarball
    '''
    def __init__(self, source, destination_dir):
        self.source = source
        self.destination = destination_dir


    def extract(self):
        '''
        Extracts the tarball into the destination directory
        '''
        if os.path.isdir(self.destination):
            shutil.rmtree(self.destination)

        if os.path.isfile(self.source) and tarfile.is_tarfile(self.source):

            name = os.path.basename(self.destination)
            temp_dir = os.path.join(os.path.dirname(self.destination),
                                    '%s.tmp' % name)
            logging.debug('Temporary directory for extracting tarball is %s' %
                          temp_dir)

            if not os.path.isdir(temp_dir):
                os.makedirs(temp_dir)

            tarball = tarfile.open(self.source)
            tarball.extractall(temp_dir)

            #
            # If there's a directory at the toplevel of the tarfile, assume
            # it's the root for the contents, usually source code
            #
            tarball_info = tarball.members[0]
            if tarball_info.isdir():
                content_path = os.path.join(temp_dir,
                                            tarball_info.name)
            else:
                content_path = temp_dir

            #
            # Now move the content directory to the final destination
            #
            shutil.move(content_path, self.destination)

        else:
            raise OSError("%s is not a file or tar file" % self.source)


    def execute(self):
        '''
        Executes all action this helper is suposed to perform

        This is the main entry point method for this class, and all other
        helper classes.
        '''
        self.extract()


class LocalTarParamHelper(LocalTarHelper):
    '''
    Helps to deal with source tarballs specified in cartersian config files

    This class attempts to make it simple to manage a tarball with source code,
    by using a  naming standard that follows this basic syntax:

    <prefix>_name_<suffix>

    <prefix> is always 'local_tar' and <suffix> sets options for this source
    tarball.  Example for source tarball named foo:

    local_tar_foo_path = /tmp/foo-1.0.tar.gz
    '''
    def __init__(self, params, name, destination_dir):
        '''
        Instantiates a new LocalTarParamHelper
        '''
        self.params = params
        self.name = name
        self.destination_dir = destination_dir
        self._parse_params()


    def _parse_params(self):
        '''
        Parses the params items for entries related to this local tar helper
        '''
        config_prefix = 'local_tar_%s' % self.name
        logging.debug('Parsing parameters for local tar %s, configuration '
                      'prefix is %s' % (self.name, config_prefix))

        self.path = self.params.get('%s_path' % config_prefix)
        logging.debug('Local source tar %s path: %s' % (self.name,
                                                        self.path))
        self.source = self.path
        self.destination = self.destination_dir


class RemoteTarHelper(LocalTarHelper):
    '''
    Helper that fetches a tarball and extracts it locally
    '''
    def __init__(self, source_uri, destination_dir):
        self.source = source_uri
        self.destination = destination_dir


    def execute(self):
        '''
        Executes all action this helper class is suposed to perform

        This is the main entry point method for this class, and all other
        helper classes.

        This implementation fetches the remote tar file and then extracts
        it using the functionality present in the parent class.
        '''
        name = os.path.basename(self.source)
        base_dest = os.path.dirname(self.destination_dir)
        dest = os.path.join(base_dest, name)
        utils.get_file(self.source, dest)
        self.source = dest
        self.extract()


class RemoteTarParamHelper(RemoteTarHelper):
    '''
    Helps to deal with remote source tarballs specified in cartersian config

    This class attempts to make it simple to manage a tarball with source code,
    by using a  naming standard that follows this basic syntax:

    <prefix>_name_<suffix>

    <prefix> is always 'local_tar' and <suffix> sets options for this source
    tarball.  Example for source tarball named foo:

    remote_tar_foo_uri = http://foo.org/foo-1.0.tar.gz
    '''
    def __init__(self, params, name, destination_dir):
        '''
        Instantiates a new RemoteTarParamHelper instance
        '''
        self.params = params
        self.name = name
        self.destination_dir = destination_dir
        self._parse_params()


    def _parse_params(self):
        '''
        Parses the params items for entries related to this remote tar helper
        '''
        config_prefix = 'remote_tar_%s' % self.name
        logging.debug('Parsing parameters for remote tar %s, configuration '
                      'prefix is %s' % (self.name, config_prefix))

        self.uri = self.params.get('%s_uri' % config_prefix)
        logging.debug('Remote source tar %s uri: %s' % (self.name,
                                                        self.uri))
        self.source = self.uri
        self.destination = self.destination_dir


class PatchHelper(object):
    '''
    Helper that encapsulates the patching of source code with patch files
    '''
    def __init__(self, source_dir, patches):
        '''
        Initializes a new PatchHelper
        '''
        self.source_dir = source_dir
        self.patches = patches


    def download(self):
        '''
        Copies patch files from remote locations to the source directory
        '''
        for patch in self.patches:
            utils.get_file(patch, os.path.join(self.source_dir,
                                               os.path.basename(patch)))


    def patch(self):
        '''
        Patches the source dir with all patch files
        '''
        os.chdir(self.source_dir)
        for patch in self.patches:
            patch_file = os.path.join(self.source_dir,
                                      os.path.basename(patch))
            utils.system('patch -p1 < %s' % os.path.basename(patch))


    def execute(self):
        '''
        Performs all steps necessary to download patches and apply them
        '''
        self.download()
        self.patch()


class PatchParamHelper(PatchHelper):
    '''
    Helps to deal with patches specified in cartersian config files

    This class attempts to make it simple to patch source coude, by using a
    naming standard that follows this basic syntax:

    [<git_repo>|<local_src>|<local_tar>|<remote_tar>]_<name>_patches

    <prefix> is either a 'local_src' or 'git_repo', that, together with <name>
    specify a directory containing source code to receive the patches. That is,
    for source code coming from git repo foo, patches would be specified as:

    git_repo_foo_patches = ['http://foo/bar.patch', 'http://foo/baz.patch']

    And for for patches to be applied on local source code named also foo:

    local_src_foo_patches = ['http://foo/bar.patch', 'http://foo/baz.patch']
    '''
    def __init__(self, params, prefix, source_dir):
        '''
        Initializes a new PatchParamHelper instance
        '''
        self.params = params
        self.prefix = prefix
        self.source_dir = source_dir
        self._parse_params()


    def _parse_params(self):
        '''
        Parses the params items for entries related to this set of patches

        This method currently does everything that the parent class __init__()
        method does, that is, sets all instance variables needed by other
        methods. That means it's not strictly necessary to call parent's
        __init__().
        '''
        logging.debug('Parsing patch parameters for prefix %s' % self.prefix)
        patches_param_key = '%s_patches' % self.prefix

        self.patches_str = self.params.get(patches_param_key, '[]')
        logging.debug('Patches config for prefix %s: %s' % (self.prefix,
                                                            self.patches_str))

        self.patches = eval(self.patches_str)
        logging.debug('Patches for prefix %s: %s' % (self.prefix,
                                                     ", ".join(self.patches)))


class GnuSourceBuildInvalidSource(Exception):
    '''
    Exception raised when build source dir/file is not valid
    '''
    pass


class SourceBuildFailed(Exception):
    '''
    Exception raised when building with parallel jobs fails

    This serves as feedback for code using *BuildHelper
    '''
    pass


class SourceBuildParallelFailed(Exception):
    '''
    Exception raised when building with parallel jobs fails

    This serves as feedback for code using *BuildHelper
    '''
    pass


class GnuSourceBuildHelper(object):
    '''
    Handles software installation of GNU-like source code

    This basically means that the build will go though the classic GNU
    autotools steps: ./configure, make, make install
    '''
    def __init__(self, source, build_dir, prefix,
                 configure_options=[]):
        '''
        @type source: string
        @param source: source directory or tarball
        @type prefix: string
        @param prefix: installation prefix
        @type build_dir: string
        @param build_dir: temporary directory used for building the source code
        @type configure_options: list
        @param configure_options: options to pass to configure
        @throws: GnuSourceBuildInvalidSource
        '''
        self.source = source
        self.build_dir = build_dir
        self.prefix = prefix
        self.configure_options = configure_options
        self.install_debug_info = True
        self.include_pkg_config_path()


    def include_pkg_config_path(self):
        '''
        Adds the current prefix to the list of paths that pkg-config searches

        This is currently not optional as there is no observed adverse side
        effects of enabling this. As the "prefix" is usually only valid during
        a test run, we believe that having other pkg-config files (*.pc) in
        either '<prefix>/share/pkgconfig' or '<prefix>/lib/pkgconfig' is
        exactly for the purpose of using them.

        @returns: None
        '''
        env_var = 'PKG_CONFIG_PATH'

        include_paths = [os.path.join(self.prefix, 'share', 'pkgconfig'),
                         os.path.join(self.prefix, 'lib', 'pkgconfig')]

        if os.environ.has_key(env_var):
            paths = os.environ[env_var].split(':')
            for include_path in include_paths:
                if include_path not in paths:
                    paths.append(include_path)
            os.environ[env_var] = ':'.join(paths)
        else:
            os.environ[env_var] = ':'.join(include_paths)

        logging.debug('PKG_CONFIG_PATH is: %s' % os.environ['PKG_CONFIG_PATH'])


    def get_configure_path(self):
        '''
        Checks if 'configure' exists, if not, return 'autogen.sh' as a fallback
        '''
        configure_path = os.path.abspath(os.path.join(self.source,
                                                      "configure"))
        autogen_path = os.path.abspath(os.path.join(self.source,
                                                "autogen.sh"))
        if os.path.exists(configure_path):
            return configure_path
        elif os.path.exists(autogen_path):
            return autogen_path
        else:
            raise GnuSourceBuildInvalidSource('configure script does not exist')


    def get_available_configure_options(self):
        '''
        Return the list of available options of a GNU like configure script

        This will run the "configure" script at the source directory

        @returns: list of options accepted by configure script
        '''
        help_raw = utils.system_output('%s --help' % self.get_configure_path(),
                                       ignore_status=True)
        help_output = help_raw.split("\n")
        option_list = []
        for line in help_output:
            cleaned_line = line.lstrip()
            if cleaned_line.startswith("--"):
                option = cleaned_line.split()[0]
                option = option.split("=")[0]
                option_list.append(option)

        return option_list


    def enable_debug_symbols(self):
        '''
        Enables option that leaves debug symbols on compiled software

        This makes debugging a lot easier.
        '''
        enable_debug_option = "--disable-strip"
        if enable_debug_option in self.get_available_configure_options():
            self.configure_options.append(enable_debug_option)
            logging.debug('Enabling debug symbols with option: %s' %
                          enable_debug_option)


    def get_configure_command(self):
        '''
        Formats configure script with all options set

        @returns: string with all configure options, including prefix
        '''
        prefix_option = "--prefix=%s" % self.prefix
        options = self.configure_options
        options.append(prefix_option)
        return "%s %s" % (self.get_configure_path(),
                          " ".join(options))


    def configure(self):
        '''
        Runs the "configure" script passing apropriate command line options
        '''
        configure_command = self.get_configure_command()
        logging.info('Running configure on build dir')
        os.chdir(self.build_dir)
        utils.system(configure_command)


    def make_parallel(self):
        '''
        Runs "make" using the correct number of parallel jobs
        '''
        parallel_make_jobs = utils.count_cpus()
        make_command = "make -j %s" % parallel_make_jobs
        logging.info("Running parallel make on build dir")
        os.chdir(self.build_dir)
        utils.system(make_command)


    def make_non_parallel(self):
        '''
        Runs "make", using a single job
        '''
        os.chdir(self.build_dir)
        utils.system("make")


    def make_clean(self):
        '''
        Runs "make clean"
        '''
        os.chdir(self.build_dir)
        utils.system("make clean")


    def make(self, failure_feedback=True):
        '''
        Runs a parallel make, falling back to a single job in failure

        @param failure_feedback: return information on build failure by raising
                                 the appropriate exceptions
        @raise: SourceBuildParallelFailed if parallel build fails, or
                SourceBuildFailed if single job build fails
        '''
        try:
            self.make_parallel()
        except error.CmdError:
            try:
                self.make_clean()
                self.make_non_parallel()
            except error.CmdError:
                if failure_feedback:
                    raise SourceBuildFailed
            if failure_feedback:
                raise SourceBuildParallelFailed


    def make_install(self):
        '''
        Runs "make install"
        '''
        os.chdir(self.build_dir)
        utils.system("make install")


    install = make_install


    def execute(self):
        '''
        Runs appropriate steps for *building* this source code tree
        '''
        if self.install_debug_info:
            self.enable_debug_symbols()
        self.configure()
        self.make()


class LinuxKernelBuildHelper(object):
    '''
    Handles Building Linux Kernel.
    '''
    def __init__(self, params, prefix, source):
        '''
        @type params: dict
        @param params: dictionary containing the test parameters
        @type source: string
        @param source: source directory or tarball
        @type prefix: string
        @param prefix: installation prefix
        '''
        self.params = params
        self.prefix = prefix
        self.source = source
        self._parse_params()


    def _parse_params(self):
        '''
        Parses the params items for entries related to guest kernel
        '''
        configure_opt_key = '%s_config' % self.prefix
        self.config = self.params.get(configure_opt_key, '')

        build_image_key = '%s_build_image' % self.prefix
        self.build_image = self.params.get(build_image_key,
                                           'arch/x86/boot/bzImage')

        build_target_key = '%s_build_target' % self.prefix
        self.build_target = self.params.get(build_target_key, 'bzImage')

        kernel_path_key = '%s_kernel_path' % self.prefix
        default_kernel_path = os.path.join('/tmp/kvm_autotest_root/images',
                                           self.build_target)
        self.kernel_path = self.params.get(kernel_path_key,
                                           default_kernel_path)

        logging.info('Parsing Linux kernel build parameters for %s',
                     self.prefix)


    def make_guest_kernel(self):
        '''
        Runs "make", using a single job
        '''
        os.chdir(self.source)
        logging.info("Building guest kernel")
        logging.debug("Kernel config is %s" % self.config)
        utils.get_file(self.config, '.config')

        # FIXME currently no support for builddir
        # run old config
        utils.system('yes "" | make oldconfig > /dev/null')
        parallel_make_jobs = utils.count_cpus()
        make_command = "make -j %s %s" % (parallel_make_jobs, self.build_target)
        logging.info("Running parallel make on src dir")
        utils.system(make_command)


    def make_clean(self):
        '''
        Runs "make clean"
        '''
        os.chdir(self.source)
        utils.system("make clean")


    def make(self, failure_feedback=True):
        '''
        Runs a parallel make

        @param failure_feedback: return information on build failure by raising
                                 the appropriate exceptions
        @raise: SourceBuildParallelFailed if parallel build fails, or
        '''
        try:
            self.make_clean()
            self.make_guest_kernel()
        except error.CmdError:
            if failure_feedback:
                raise SourceBuildParallelFailed


    def cp_linux_kernel(self):
        '''
        Copying Linux kernel to target path
        '''
        os.chdir(self.source)
        utils.force_copy(self.build_image, self.kernel_path)


    install = cp_linux_kernel


    def execute(self):
        '''
        Runs appropriate steps for *building* this source code tree
        '''
        self.make()


class GnuSourceBuildParamHelper(GnuSourceBuildHelper):
    '''
    Helps to deal with gnu_autotools build helper in cartersian config files

    This class attempts to make it simple to build source coude, by using a
    naming standard that follows this basic syntax:

    [<git_repo>|<local_src>]_<name>_<option> = value

    To pass extra options to the configure script, while building foo from a
    git repo, set the following variable:

    git_repo_foo_configure_options = --enable-feature
    '''
    def __init__(self, params, name, destination_dir, install_prefix):
        '''
        Instantiates a new GnuSourceBuildParamHelper
        '''
        self.params = params
        self.name = name
        self.destination_dir = destination_dir
        self.install_prefix = install_prefix
        self._parse_params()


    def _parse_params(self):
        '''
        Parses the params items for entries related to source directory

        This method currently does everything that the parent class __init__()
        method does, that is, sets all instance variables needed by other
        methods. That means it's not strictly necessary to call parent's
        __init__().
        '''
        logging.debug('Parsing gnu_autotools build parameters for %s' %
                      self.name)

        configure_opt_key = '%s_configure_options' % self.name
        configure_options = self.params.get(configure_opt_key, '').split()
        logging.debug('Configure options for %s: %s' % (self.name,
                                                        configure_options))

        self.source = self.destination_dir
        self.build_dir = self.destination_dir
        self.prefix = self.install_prefix
        self.configure_options = configure_options
        self.include_pkg_config_path()

        # Support the install_debug_info feature, that automatically
        # adds/keeps debug information on generated libraries/binaries
        install_debug_info_cfg = self.params.get("install_debug_info", "yes")
        self.install_debug_info = install_debug_info_cfg != "no"


def install_host_kernel(job, params):
    """
    Install a host kernel, given the appropriate params.

    @param job: Job object.
    @param params: Dict with host kernel install params.
    """
    install_type = params.get('host_kernel_install_type')

    if install_type == 'rpm':
        logging.info('Installing host kernel through rpm')

        rpm_url = params.get('host_kernel_rpm_url')

        dst = os.path.join("/tmp", os.path.basename(rpm_url))
        k = utils.get_file(rpm_url, dst)
        host_kernel = job.kernel(k)
        host_kernel.install(install_vmlinux=False)
        host_kernel.boot()

    elif install_type in ['koji', 'brew']:
        logging.info('Installing host kernel through koji/brew')

        koji_cmd = params.get('host_kernel_koji_cmd')
        koji_build = params.get('host_kernel_koji_build')
        koji_tag = params.get('host_kernel_koji_tag')

        k_deps = KojiPkgSpec(tag=koji_tag, build=koji_build, package='kernel',
                             subpackages=['kernel-devel', 'kernel-firmware'])
        k = KojiPkgSpec(tag=koji_tag, build=koji_build, package='kernel',
                        subpackages=['kernel'])

        c = KojiClient(koji_cmd)
        logging.info('Fetching kernel dependencies (-devel, -firmware)')
        c.get_pkgs(k_deps, job.tmpdir)
        logging.info('Installing kernel dependencies (-devel, -firmware) '
                     'through %s', install_type)
        k_deps_rpm_file_names = [os.path.join(job.tmpdir, rpm_file_name) for
                                 rpm_file_name in c.get_pkg_rpm_file_names(k_deps)]
        utils.run('rpm -U --force %s' % " ".join(k_deps_rpm_file_names))

        c.get_pkgs(k, job.tmpdir)
        k_rpm = os.path.join(job.tmpdir,
                             c.get_pkg_rpm_file_names(k)[0])
        host_kernel = job.kernel(k_rpm)
        host_kernel.install(install_vmlinux=False)
        host_kernel.boot()

    elif install_type == 'git':
        logging.info('Chose to install host kernel through git, proceeding')

        repo = params.get('host_kernel_git_repo')
        repo_base = params.get('host_kernel_git_repo_base', None)
        branch = params.get('host_kernel_git_branch')
        commit = params.get('host_kernel_git_commit')
        patch_list = params.get('host_kernel_patch_list')
        if patch_list:
            patch_list = patch_list.split()
        kernel_config = params.get('host_kernel_config', None)

        repodir = os.path.join("/tmp", 'kernel_src')
        r = git.get_repo(uri=repo, branch=branch, destination_dir=repodir,
                         commit=commit, base_uri=repo_base)
        host_kernel = job.kernel(r)
        if patch_list:
            host_kernel.patch(patch_list)
        if kernel_config:
            host_kernel.config(kernel_config)
        host_kernel.build()
        host_kernel.install()
        host_kernel.boot()

    else:
        logging.info('Chose %s, using the current kernel for the host',
                     install_type)


def if_nametoindex(ifname):
    """
    Map an interface name into its corresponding index.
    Returns 0 on error, as 0 is not a valid index

    @param ifname: interface name
    """
    index = 0
    ctrl_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, 0)
    ifr = struct.pack("16si", ifname, 0)
    r = fcntl.ioctl(ctrl_sock, SIOCGIFINDEX, ifr)
    index = struct.unpack("16si", r)[1]
    ctrl_sock.close()
    return index


def vnet_hdr_probe(tapfd):
    """
    Check if the IFF_VNET_HDR is support by tun.

    @param tapfd: the file descriptor of /dev/net/tun
    """
    u = struct.pack("I", 0)
    try:
        r = fcntl.ioctl(tapfd, TUNGETFEATURES, u)
    except OverflowError:
        return False
    flags = struct.unpack("I", r)[0]
    if flags & IFF_VNET_HDR:
        return True
    else:
        return False


def open_tap(devname, ifname, vnet_hdr=True):
    """
    Open a tap device and returns its file descriptor which is used by
    fd=<fd> parameter of qemu-kvm.

    @param ifname: TAP interface name
    @param vnet_hdr: Whether enable the vnet header
    """
    try:
        tapfd = os.open(devname, os.O_RDWR)
    except OSError, e:
        raise TAPModuleError(devname, "open", e)
    flags = IFF_TAP | IFF_NO_PI
    if vnet_hdr and vnet_hdr_probe(tapfd):
        flags |= IFF_VNET_HDR

    ifr = struct.pack("16sh", ifname, flags)
    try:
        r = fcntl.ioctl(tapfd, TUNSETIFF, ifr)
    except IOError, details:
        raise TAPCreationError(ifname, details)
    ifname = struct.unpack("16sh", r)[0].strip("\x00")
    return tapfd


def add_to_bridge(ifname, brname):
    """
    Add a TAP device to bridge

    @param ifname: Name of TAP device
    @param brname: Name of the bridge
    """
    ctrl_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, 0)
    index = if_nametoindex(ifname)
    if index == 0:
        raise TAPNotExistError(ifname)
    ifr = struct.pack("16si", brname, index)
    try:
        r = fcntl.ioctl(ctrl_sock, SIOCBRADDIF, ifr)
    except IOError, details:
        raise BRAddIfError(ifname, brname, details)
    ctrl_sock.close()


def bring_up_ifname(ifname):
    """
    Bring up an interface

    @param ifname: Name of the interface
    """
    ctrl_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, 0)
    ifr = struct.pack("16sh", ifname, IFF_UP)
    try:
        fcntl.ioctl(ctrl_sock, SIOCSIFFLAGS, ifr)
    except IOError:
        raise TAPBringUpError(ifname)
    ctrl_sock.close()


def if_set_macaddress(ifname, mac):
    """
    Set the mac address for an interface

    @param ifname: Name of the interface
    @mac: Mac address
    """
    ctrl_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, 0)

    ifr = struct.pack("256s", ifname)
    try:
        mac_dev = fcntl.ioctl(ctrl_sock, SIOCGIFHWADDR, ifr)[18:24]
        mac_dev = ":".join(["%02x" % ord(m) for m in mac_dev])
    except IOError, e:
        raise HwAddrGetError(ifname)

    if mac_dev.lower() == mac.lower():
        return

    ifr = struct.pack("16sH14s", ifname, 1,
                      "".join([chr(int(m, 16)) for m in mac.split(":")]))
    try:
        fcntl.ioctl(ctrl_sock, SIOCSIFHWADDR, ifr)
    except IOError, e:
        logging.info(e)
        raise HwAddrSetError(ifname, mac)
    ctrl_sock.close()


def check_iso(url, destination, iso_sha1):
    """
    Verifies if ISO that can be find on url is on destination with right hash.

    This function will verify the SHA1 hash of the ISO image. If the file
    turns out to be missing or corrupted, let the user know we can download it.

    @param url: URL where the ISO file can be found.
    @param destination: Directory in local disk where we'd like the iso to be.
    @param iso_sha1: SHA1 hash for the ISO image.
    """
    file_ok = False
    if not os.path.isdir(destination):
        os.makedirs(destination)
    iso_path = os.path.join(destination, os.path.basename(url))
    if not os.path.isfile(iso_path):
        logging.warning("File %s not found", iso_path)
        logging.warning("Expected SHA1 sum: %s", iso_sha1)
        answer = utils.ask("Would you like to download it from %s?" % url)
        if answer == 'y':
            utils.interactive_download(url, iso_path, 'ISO Download')
        else:
            logging.warning("Missing file %s", iso_path)
            logging.warning("Please download it or put an existing copy on the "
                            "appropriate location")
            return
    else:
        logging.info("Found %s", iso_path)
        logging.info("Expected SHA1 sum: %s", iso_sha1)
        answer = utils.ask("Would you like to check %s? It might take a while" %
                           iso_path)
        if answer == 'y':
            actual_iso_sha1 = utils.hash_file(iso_path, method='sha1')
            if actual_iso_sha1 != iso_sha1:
                logging.error("Actual SHA1 sum: %s", actual_iso_sha1)
            else:
                logging.info("SHA1 sum check OK")
        else:
            logging.info("File %s present, but chose to not verify it",
                         iso_path)
            return

    if file_ok:
        logging.info("%s present, with proper checksum", iso_path)


def virt_test_assistant(test_name, test_dir, base_dir, default_userspace_paths,
                        check_modules, online_docs_url):
    """
    Common virt test assistant module.

    @param test_name: Test name, such as "kvm".
    @param test_dir: Path with the test directory.
    @param base_dir: Base directory used to hold images and isos.
    @param default_userspace_paths: Important programs for a successful test
            execution.
    @param check_modules: Whether we want to verify if a given list of modules
            is loaded in the system.
    @param online_docs_url: URL to an online documentation system, such as an
            wiki page.
    """
    logging_manager.configure_logging(VirtLoggingConfig(), verbose=True)
    logging.info("%s test config helper", test_name)
    step = 0
    common_dir = os.path.dirname(sys.modules[__name__].__file__)
    logging.info("")
    step += 1
    logging.info("%d - Verifying directories (check if the directory structure "
                 "expected by the default test config is there)", step)
    sub_dir_list = ["images", "isos", "steps_data"]
    for sub_dir in sub_dir_list:
        sub_dir_path = os.path.join(base_dir, sub_dir)
        if not os.path.isdir(sub_dir_path):
            logging.debug("Creating %s", sub_dir_path)
            os.makedirs(sub_dir_path)
        else:
            logging.debug("Dir %s exists, not creating" %
                          sub_dir_path)
    logging.info("")
    step += 1
    logging.info("%d - Creating config files from samples (copy the default "
                 "config samples to actual config files)", step)
    config_file_list = glob.glob(os.path.join(test_dir, "*.cfg.sample"))
    config_file_list += glob.glob(os.path.join(common_dir, "*.cfg.sample"))
    for config_file in config_file_list:
        src_file = config_file
        dst_file = os.path.join(test_dir, os.path.basename(config_file))
        dst_file = dst_file.rstrip(".sample")
        if not os.path.isfile(dst_file):
            logging.debug("Creating config file %s from sample", dst_file)
            shutil.copyfile(src_file, dst_file)
        else:
            diff_result = utils.run("diff -Naur %s %s" % (dst_file, src_file),
                                    ignore_status=True, verbose=False)
            if diff_result.exit_status != 0:
                logging.debug("%s result:\n %s" %
                              (diff_result.command, diff_result.stdout))
                answer = utils.ask("Config file  %s differs from %s. Overwrite?"
                                   % (dst_file,src_file))
                if answer == "y":
                    logging.debug("Restoring config file %s from sample" %
                                  dst_file)
                    shutil.copyfile(src_file, dst_file)
                else:
                    logging.debug("Preserving existing %s file" % dst_file)
            else:
                logging.debug("Config file %s exists, not touching" % dst_file)

    logging.info("")
    step += 1
    logging.info("%s - Verifying iso (make sure we have the OS ISO needed for "
                 "the default test set)", step)

    iso_name = "Fedora-17-x86_64-DVD.iso"
    fedora_dir = "pub/fedora/linux/releases/17/Fedora/x86_64/iso"
    url = os.path.join("http://download.fedoraproject.org/", fedora_dir,
                       iso_name)
    iso_sha1 = "7a748072cc366ee3bdcd533afc70eda239c977c7"
    destination = os.path.join(base_dir, 'isos', 'linux')
    check_iso(url, destination, iso_sha1)

    logging.info("")
    step += 1
    logging.info("%d - Verifying winutils.iso (make sure we have the utility "
                 "ISO needed for Windows testing)", step)

    logging.info("In order to run the KVM autotests in Windows guests, we "
                 "provide you an ISO that this script can download")

    url = "http://people.redhat.com/mrodrigu/kvm/winutils.iso"
    iso_sha1 = "02930224756510e383c44c49bffb760e35d6f892"
    destination = os.path.join(base_dir, 'isos', 'windows')
    path = os.path.join(destination, iso_name)
    check_iso(url, destination, iso_sha1)

    logging.info("")
    step += 1
    logging.info("%d - Checking if the appropriate userspace programs are "
                 "installed", step)
    for path in default_userspace_paths:
        if not os.path.isfile(path):
            logging.warning("No %s found. You might need to install %s.",
                            path, os.path.basename(path))
        else:
            logging.debug("%s present", path)
    logging.info("If you wish to change any userspace program path, "
                 "you will have to modify tests.cfg")

    if check_modules:
        logging.info("")
        step += 1
        logging.info("%d - Checking for modules %s", step,
                     ",".join(check_modules))
        for module in check_modules:
            if not utils.module_is_loaded(module):
                logging.warning("Module %s is not loaded. You might want to "
                                "load it", module)
            else:
                logging.debug("Module %s loaded", module)

    if online_docs_url:
        logging.info("")
        step += 1
        logging.info("%d - Verify needed packages to get started", step)
        logging.info("Please take a look at the online documentation: %s",
                     online_docs_url)

    client_dir = os.path.abspath(os.path.join(test_dir, "..", ".."))
    autotest_bin = os.path.join(client_dir, 'bin', 'autotest')
    control_file = os.path.join(test_dir, 'control')

    logging.info("")
    logging.info("When you are done fixing eventual warnings found, "
                 "you can run the test using this command line AS ROOT:")
    logging.info("%s %s", autotest_bin, control_file)
    logging.info("Autotest prints the results dir, so you can look at DEBUG "
                 "logs if something went wrong")
    logging.info("You can also edit the test config files")


def create_x509_dir(path, cacert_subj, server_subj, passphrase,
                    secure=False, bits=1024, days=1095):
    """
    Creates directory with freshly generated:
    ca-cart.pem, ca-key.pem, server-cert.pem, server-key.pem,

    @param path: defines path to directory which will be created
    @param cacert_subj: ca-cert.pem subject
    @param server_key.csr subject
    @param passphrase - passphrase to ca-key.pem
    @param secure = False - defines if the server-key.pem will use a passphrase
    @param bits = 1024: bit length of keys
    @param days = 1095: cert expiration

    @raise ValueError: openssl not found or rc != 0
    @raise OSError: if os.makedirs() fails
    """

    ssl_cmd = os_dep.command("openssl")
    path = path + os.path.sep # Add separator to the path
    shutil.rmtree(path, ignore_errors = True)
    os.makedirs(path)

    server_key = "server-key.pem.secure"
    if secure:
        server_key = "server-key.pem"

    cmd_set = [
    ('%s genrsa -des3 -passout pass:%s -out %sca-key.pem %d' %
     (ssl_cmd, passphrase, path, bits)),
    ('%s req -new -x509 -days %d -key %sca-key.pem -passin pass:%s -out '
     '%sca-cert.pem -subj "%s"' %
     (ssl_cmd, days, path, passphrase, path, cacert_subj)),
    ('%s genrsa -out %s %d' % (ssl_cmd, path + server_key, bits)),
    ('%s req -new -key %s -out %s/server-key.csr -subj "%s"' %
     (ssl_cmd, path + server_key, path, server_subj)),
    ('%s x509 -req -passin pass:%s -days %d -in %sserver-key.csr -CA '
     '%sca-cert.pem -CAkey %sca-key.pem -set_serial 01 -out %sserver-cert.pem' %
     (ssl_cmd, passphrase, days, path, path, path, path))
     ]

    if not secure:
        cmd_set.append('%s rsa -in %s -out %sserver-key.pem' %
                       (ssl_cmd, path + server_key, path))

    for cmd in cmd_set:
        utils.run(cmd)
        logging.info(cmd)


class NumaNode(object):
    """
    Numa node to control processes and shared memory.
    """
    def __init__(self, i=-1):
        self.num = self.get_node_num()
        if i < 0:
            self.cpus = self.get_node_cpus(int(self.num) + i).split()
        else:
            self.cpus = self.get_node_cpus(i - 1).split()
        self.dict = {}
        for i in self.cpus:
            self.dict[i] = "free"


    def get_node_num(self):
        """
        Get the number of nodes of current host.
        """
        cmd = utils.run("numactl --hardware")
        return re.findall("available: (\d+) nodes", cmd.stdout)[0]


    def get_node_cpus(self, i):
        """
        Get cpus of a specific node

        @param i: Index of the CPU inside the node.
        """
        cmd = utils.run("numactl --hardware")
        return re.findall("node %s cpus: (.*)" % i, cmd.stdout)[0]


    def free_cpu(self, i):
        """
        Release pin of one node.

        @param i: Index of the node.
        """
        self.dict[i] = "free"


    def _flush_pin(self):
        """
        Flush pin dict, remove the record of exited process.
        """
        cmd = utils.run("ps -eLf | awk '{print $4}'")
        all_pids = cmd.stdout
        for i in self.cpus:
            if self.dict[i] != "free" and self.dict[i] not in all_pids:
                self.free_cpu(i)


    @error.context_aware
    def pin_cpu(self, process):
        """
        Pin one process to a single cpu.

        @param process: Process ID.
        """
        self._flush_pin()
        error.context("Pinning process %s to the CPU" % process)
        for i in self.cpus:
            if self.dict[i] == "free":
                self.dict[i] = str(process)
                cmd = "taskset -p %s %s" % (hex(2 ** int(i)), process)
                logging.debug("NumaNode (%s): " % i + cmd)
                utils.run(cmd)
                return i


    def show(self):
        """
        Display the record dict in a convenient way.
        """
        logging.info("Numa Node record dict:")
        for i in self.cpus:
            logging.info("    %s: %s" % (i, self.dict[i]))


def generate_mac_address_simple():
    r = random.SystemRandom()
    mac = "9a:%02x:%02x:%02x:%02x:%02x" % (r.randint(0x00, 0xff),
                                           r.randint(0x00, 0xff),
                                           r.randint(0x00, 0xff),
                                           r.randint(0x00, 0xff),
                                           r.randint(0x00, 0xff))
    return mac


def guest_active(vm):
    o = vm.monitor.info("status")
    if isinstance(o, str):
        return "status: running" in o
    else:
        return o.get("status") == "running"


def preprocess_images(bindir, params, env):
    # Clone master image form vms.
    for vm_name in params.get("vms").split():
        vm = env.get_vm(vm_name)
        if vm:
            vm.destroy(free_mac_addresses=False)
        vm_params = params.object_params(vm_name)
        for image in vm_params.get("master_images_clone").split():
            clone_image(params, vm_name, image, bindir)


def postprocess_images(bindir, params):
    for vm in params.get("vms").split():
        vm_params = params.object_params(vm)
        for image in vm_params.get("master_images_clone").split():
            rm_image(params, vm, image, bindir)


class MigrationData(object):
    def __init__(self, params, srchost, dsthost, vms_name, params_append):
        """
        Class that contains data needed for one migration.
        """
        self.params = params.copy()
        self.params.update(params_append)

        self.source = False
        if params.get("hostid") == srchost:
            self.source = True

        self.destination = False
        if params.get("hostid") == dsthost:
            self.destination = True

        self.src = srchost
        self.dst = dsthost
        self.hosts = [srchost, dsthost]
        self.mig_id = {'src': srchost, 'dst': dsthost, "vms": vms_name}
        self.vms_name = vms_name
        self.vms = []
        self.vm_ports = None


    def is_src(self):
        """
        @return: True if host is source.
        """
        return self.source


    def is_dst(self):
        """
        @return: True if host is destination.
        """
        return self.destination


class MultihostMigration(object):
    """
    Class that provides a framework for multi-host migration.

    Migration can be run both synchronously and asynchronously.
    To specify what is going to happen during the multi-host
    migration, it is necessary to reimplement the method
    migration_scenario. It is possible to start multiple migrations
    in separate threads, since self.migrate is thread safe.

    Only one test using multihost migration framework should be
    started on one machine otherwise it is necessary to solve the
    problem with listen server port.

    Multihost migration starts SyncListenServer through which
    all messages are transfered, since the multiple hosts can
    be in diferent states.

    Class SyncData is used to transfer data over network or
    synchronize the migration process. Synchronization sessions
    are recognized by session_id.

    It is important to note that, in order to have multi-host
    migration, one needs shared guest image storage. The simplest
    case is when the guest images are on an NFS server.

    Example:
        class TestMultihostMigration(virt_utils.MultihostMigration):
            def __init__(self, test, params, env):
                super(testMultihostMigration, self).__init__(test, params, env)

            def migration_scenario(self):
                srchost = self.params.get("hosts")[0]
                dsthost = self.params.get("hosts")[1]

                def worker(mig_data):
                    vm = env.get_vm("vm1")
                    session = vm.wait_for_login(timeout=self.login_timeout)
                    session.sendline("nohup dd if=/dev/zero of=/dev/null &")
                    session.cmd("killall -0 dd")

                def check_worker(mig_data):
                    vm = env.get_vm("vm1")
                    session = vm.wait_for_login(timeout=self.login_timeout)
                    session.cmd("killall -9 dd")

                # Almost synchronized migration, waiting to end it.
                # Work is started only on first VM.
                self.migrate_wait(["vm1", "vm2"], srchost, dsthost,
                                  worker, check_worker)

                # Migration started in different threads.
                # It allows to start multiple migrations simultaneously.
                mig1 = self.migrate(["vm1"], srchost, dsthost,
                                    worker, check_worker)
                mig2 = self.migrate(["vm2"], srchost, dsthost)
                mig2.join()
                mig1.join()

    mig = TestMultihostMigration(test, params, env)
    mig.run()
    """
    def __init__(self, test, params, env, preprocess_env=True):
        self.test = test
        self.params = params
        self.env = env
        self.hosts = params.get("hosts")
        self.hostid = params.get('hostid', "")
        self.comm_port = int(params.get("comm_port", 13234))
        vms_count = len(params["vms"].split())

        self.login_timeout = int(params.get("login_timeout", 360))
        self.disk_prepare_timeout = int(params.get("disk_prepare_timeout",
                                              160 * vms_count))
        self.finish_timeout = int(params.get("finish_timeout",
                                              120 * vms_count))

        self.new_params = None

        if params.get("clone_master") == "yes":
            self.clone_master = True
        else:
            self.clone_master = False

        self.mig_timeout = int(params.get("mig_timeout"))
        # Port used to communicate info between source and destination
        self.regain_ip_cmd = params.get("regain_ip_cmd", "dhclient")

        self.vm_lock = threading.Lock()

        self.sync_server = None
        if self.clone_master:
            self.sync_server = SyncListenServer()

        if preprocess_env:
            self.preprocess_env()
            self._hosts_barrier(self.hosts, self.hosts, 'disk_prepared',
                                 self.disk_prepare_timeout)


    def migration_scenario(self):
        """
        Multi Host migration_scenario is started from method run where the
        exceptions are checked. It is not necessary to take care of
        cleaning up after test crash or finish.
        """
        raise NotImplementedError


    def migrate_vms_src(self, mig_data):
        """
        Migrate vms source.

        @param mig_Data: Data for migration.

        For change way how machine migrates is necessary
        re implement this method.
        """
        def mig_wrapper(vm, dsthost, vm_ports):
            vm.migrate(dest_host=dsthost, remote_port=vm_ports[vm.name])

        logging.info("Start migrating now...")
        multi_mig = []
        for vm in mig_data.vms:
            multi_mig.append((mig_wrapper, (vm, mig_data.dst,
                                            mig_data.vm_ports)))
        parallel(multi_mig)


    def migrate_vms_dest(self, mig_data):
        """
        Migrate vms destination. This function is started on dest host during
        migration.

        @param mig_Data: Data for migration.
        """
        pass


    def __del__(self):
        if self.sync_server:
            self.sync_server.close()


    def master_id(self):
        return self.hosts[0]


    def _hosts_barrier(self, hosts, session_id, tag, timeout):
        logging.debug("Barrier timeout: %d tags: %s" % (timeout, tag))
        tags = SyncData(self.master_id(), self.hostid, hosts,
                        "%s,%s,barrier" % (str(session_id), tag),
                        self.sync_server).sync(tag, timeout)
        logging.debug("Barrier tag %s" % (tags))


    def preprocess_env(self):
        """
        Prepare env to start vms.
        """
        preprocess_images(self.test.bindir, self.params, self.env)


    def _check_vms_source(self, mig_data):
        for vm in mig_data.vms:
            vm.wait_for_login(timeout=self.login_timeout)

        sync = SyncData(self.master_id(), self.hostid, mig_data.hosts,
                        mig_data.mig_id, self.sync_server)
        mig_data.vm_ports = sync.sync(timeout=120)[mig_data.dst]
        logging.info("Received from destination the migration port %s",
                     str(mig_data.vm_ports))


    def _check_vms_dest(self, mig_data):
        mig_data.vm_ports = {}
        for vm in mig_data.vms:
            logging.info("Communicating to source migration port %s",
                         vm.migration_port)
            mig_data.vm_ports[vm.name] = vm.migration_port

        SyncData(self.master_id(), self.hostid,
                 mig_data.hosts, mig_data.mig_id,
                 self.sync_server).sync(mig_data.vm_ports, timeout=120)


    def _prepare_params(self, mig_data):
        """
        Prepare separate params for vm migration.

        @param vms_name: List of vms.
        """
        new_params = mig_data.params.copy()
        new_params["vms"] = " ".join(mig_data.vms_name)
        return new_params


    def _check_vms(self, mig_data):
        """
        Check if vms are started correctly.

        @param vms: list of vms.
        @param source: Must be True if is source machine.
        """
        logging.info("Try check vms %s" % (mig_data.vms_name))
        for vm in mig_data.vms_name:
            if not self.env.get_vm(vm) in mig_data.vms:
                mig_data.vms.append(self.env.get_vm(vm))
        for vm in mig_data.vms:
            logging.info("Check vm %s on host %s" % (vm.name, self.hostid))
            vm.verify_alive()

        if mig_data.is_src():
            self._check_vms_source(mig_data)
        else:
            self._check_vms_dest(mig_data)


    def prepare_for_migration(self, mig_data, migration_mode):
        """
        Prepare destination of migration for migration.

        @param mig_data: Class with data necessary for migration.
        @param migration_mode: Migration mode for prepare machine.
        """
        new_params = self._prepare_params(mig_data)

        new_params['migration_mode'] = migration_mode
        new_params['start_vm'] = 'yes'
        self.vm_lock.acquire()
        virt_env_process.process(self.test, new_params, self.env,
                                 virt_env_process.preprocess_image,
                                 virt_env_process.preprocess_vm)
        self.vm_lock.release()

        self._check_vms(mig_data)


    def migrate_vms(self, mig_data):
        """
        Migrate vms.
        """
        if mig_data.is_src():
            self.migrate_vms_src(mig_data)
        else:
            self.migrate_vms_dest(mig_data)


    def check_vms(self, mig_data):
        """
        Check vms after migrate.

        @param mig_data: object with migration data.
        """
        for vm in mig_data.vms:
            if not guest_active(vm):
                raise error.TestFail("Guest not active after migration")

        logging.info("Migrated guest appears to be running")

        logging.info("Logging into migrated guest after migration...")
        for vm in mig_data.vms:
            session_serial = vm.wait_for_serial_login(timeout=
                                                      self.login_timeout)
            #There is sometime happen that system sends some message on
            #serial console and IP renew command block test. Because
            #there must be added "sleep" in IP renew command.
            session_serial.cmd(self.regain_ip_cmd)
            vm.wait_for_login(timeout=self.login_timeout)


    def postprocess_env(self):
        """
        Kill vms and delete cloned images.
        """
        postprocess_images(self.test.bindir, self.params)


    def migrate(self, vms_name, srchost, dsthost, start_work=None,
                check_work=None, mig_mode="tcp", params_append=None):
        """
        Migrate machine from srchost to dsthost. It executes start_work on
        source machine before migration and executes check_work on dsthost
        after migration.

        Migration execution progress:

        source host                   |   dest host
        --------------------------------------------------------
           prepare guest on both sides of migration
            - start machine and check if machine works
            - synchronize transfer data needed for migration
        --------------------------------------------------------
        start work on source guests   |   wait for migration
        --------------------------------------------------------
                     migrate guest to dest host.
              wait on finish migration synchronization
        --------------------------------------------------------
                                      |   check work on vms
        --------------------------------------------------------
                    wait for sync on finish migration

        @param vms_name: List of vms.
        @param srchost: src host id.
        @param dsthost: dst host id.
        @param start_work: Function started before migration.
        @param check_work: Function started after migration.
        @param mig_mode: Migration mode.
        @param params_append: Append params to self.params only for migration.
        """
        def migrate_wrap(vms_name, srchost, dsthost, start_work=None,
                check_work=None, params_append=None):
            logging.info("Starting migrate vms %s from host %s to %s" %
                         (vms_name, srchost, dsthost))
            error = None
            mig_data = MigrationData(self.params, srchost, dsthost,
                                     vms_name, params_append)
            try:
                try:
                    if mig_data.is_src():
                        self.prepare_for_migration(mig_data, None)
                    elif self.hostid == dsthost:
                        self.prepare_for_migration(mig_data, mig_mode)
                    else:
                        return

                    if mig_data.is_src():
                        if start_work:
                            start_work(mig_data)

                    self.migrate_vms(mig_data)

                    timeout = 30
                    if not mig_data.is_src():
                        timeout = self.mig_timeout
                    self._hosts_barrier(mig_data.hosts, mig_data.mig_id,
                                        'mig_finished', timeout)

                    if mig_data.is_dst():
                        self.check_vms(mig_data)
                        if check_work:
                            check_work(mig_data)

                except:
                    error = True
                    raise
            finally:
                if not error:
                    self._hosts_barrier(self.hosts,
                                        mig_data.mig_id,
                                        'test_finihed',
                                        self.finish_timeout)

        def wait_wrap(vms_name, srchost, dsthost):
            mig_data = MigrationData(self.params, srchost, dsthost, vms_name,
                                     None)
            timeout = (self.login_timeout + self.mig_timeout +
                       self.finish_timeout)

            self._hosts_barrier(self.hosts, mig_data.mig_id,
                                'test_finihed', timeout)

        if (self.hostid in [srchost, dsthost]):
            mig_thread = utils.InterruptedThread(migrate_wrap, (vms_name,
                                                                srchost,
                                                                dsthost,
                                                                start_work,
                                                                check_work,
                                                                params_append))
        else:
            mig_thread = utils.InterruptedThread(wait_wrap, (vms_name,
                                                             srchost,
                                                             dsthost))
        mig_thread.start()
        return mig_thread


    def migrate_wait(self, vms_name, srchost, dsthost, start_work=None,
                      check_work=None, mig_mode="tcp", params_append=None):
        """
        Migrate machine from srchost to dsthost and wait for finish.
        It executes start_work on source machine before migration and executes
        check_work on dsthost after migration.

        @param vms_name: List of vms.
        @param srchost: src host id.
        @param dsthost: dst host id.
        @param start_work: Function which is started before migration.
        @param check_work: Function which is started after
                           done of migration.
        """
        self.migrate(vms_name, srchost, dsthost, start_work, check_work,
                     mig_mode, params_append).join()


    def cleanup(self):
        """
        Cleanup env after test.
        """
        if self.clone_master:
            self.sync_server.close()
            self.postprocess_env()


    def run(self):
        """
        Start multihost migration scenario.
        After scenario is finished or if scenario crashed it calls postprocess
        machines and cleanup env.
        """
        try:
            self.migration_scenario()

            self._hosts_barrier(self.hosts, self.hosts, 'all_test_finihed',
                                self.finish_timeout)
        finally:
            self.cleanup()

def get_ip_address_by_interface(ifname):
    """
    returns ip address by interface
    @param ifname - interface name
    @raise NetError - When failed to fetch IP address (ioctl raised IOError.).

    Retrieves interface address from socket fd trough ioctl call
    and transforms it into string from 32-bit packed binary
    by using socket.inet_ntoa().

    """
    SIOCGIFADDR = 0x8915 # Get interface address <bits/ioctls.h>
    mysocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        return socket.inet_ntoa(fcntl.ioctl(
                    mysocket.fileno(),
                    SIOCGIFADDR,
                    struct.pack('256s', ifname[:15]) # ifname to binary IFNAMSIZ == 16
                )[20:24])
    except IOError:
        raise NetError("Error while retrieving IP address from interface %s." % ifname)
