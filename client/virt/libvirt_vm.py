"""
Utility classes and functions to handle Virtual Machine creation using libvirt.

@copyright: 2011 Red Hat Inc.
"""

import time, os, logging, fcntl, re, commands, shutil, urlparse, tempfile
from autotest.client.shared import error
from autotest.client import utils, os_dep
from xml.dom import minidom
import virt_utils, virt_vm, virt_storage, aexpect, virt_remote

DEBUG = False
try:
    VIRSH_EXEC = os_dep.command("virsh")
except ValueError:
    VIRSH_EXEC = None


def libvirtd_restart():
    """
    Restart libvirt daemon.
    """
    try:
        utils.run("service libvirtd restart")
        logging.debug("Restarted libvirtd successfuly")
        return True
    except error.CmdError, detail:
        logging.error("Failed to restart libvirtd:\n%s", detail)
        return False


def libvirtd_stop():
    """
    Stop libvirt daemon.
    """
    try:
        utils.run("service libvirtd stop")
        logging.debug("Stop  libvirtd successfuly")
        return True
    except error.CmdError, detail:
        logging.error("Failed to stop libvirtd:\n%s", detail)
        return False


def libvirtd_start():
    """
    Start libvirt daemon.
    """
    try:
        utils.run("service libvirtd  start")
        logging.debug("Start  libvirtd successfuly")
        return True
    except error.CmdError, detail:
        logging.error("Failed to start libvirtd:\n%s", detail)
        return False


def service_libvirtd_control(action):
    """
    Libvirtd control by action, if cmd executes successfully,
    return True, otherwise return False.
    If the action is status, return True when it's running,
    otherwise return False.
    @ param action: start|stop|status|restart|condrestart|
      reload|force-reload|try-restart
    """
    actions = ['start','stop','restart','condrestart','reload',
               'force-reload','try-restart']
    if action in actions:
        try:
            utils.run("service libvirtd %s" % action)
            logging.debug("%s libvirtd successfuly", action)
            return True
        except error.CmdError, detail:
            logging.error("Failed to %s libvirtd:\n%s", action, detail)
            return False
    elif action == "status":
        cmd_result = utils.run("service libvirtd status")
        if re.search("pid", cmd_result.stdout.strip()):
            logging.info("Libvirtd service is running")
            return True
        else:
            return False
    else:
        raise error.TestError("Unknown action: %s" % action)


def virsh_cmd(cmd, uri="", ignore_status=False, print_info=False):
    """
    Append cmd to 'virsh' and execute, optionally return full results.

    @param: cmd: Command line to append to virsh command
    @param: uri: Hypervisor URI to connect to
    @param: ignore_status: Raise an exception if False
    @param: print_info: Print stdout and stderr if True
    @return: CmdResult object
    """
    if VIRSH_EXEC is None:
        raise ValueError('Missing command: virsh')

    uri_arg = ""
    if uri:
        uri_arg = "-c " + uri
    cmd = "%s %s %s" % (VIRSH_EXEC, uri_arg, cmd)

    if print_info:
        logging.debug("Running command: %s" % cmd)

    ret = utils.run(cmd, verbose=DEBUG, ignore_status=ignore_status)

    if print_info:
        logging.debug("status: %s" % ret.exit_status)
        logging.debug("stdout: %s" % ret.stdout.strip())
        logging.debug("stderr: %s" % ret.stderr.strip())
    return ret


def virsh_domname(id, uri="", ignore_status=False, print_info=False):
    """
    Convert a domain id or UUID to domain name

    @param id: a domain id or UUID.
    """
    return virsh_cmd("domname --domain %s" % id, uri,
                                ignore_status, print_info)


def virsh_qemu_monitor_command(domname, command, uri="",
                               ignore_status=False, print_info=False):
    """
    This helps to execute the qemu monitor command through virsh command.
    """

    cmd_qemu_monitor = "qemu-monitor-command %s --hmp \'%s\'" % (domname, command)
    return virsh_cmd(cmd_qemu_monitor, uri, ignore_status, print_info)


def virsh_vcpupin(domname, vcpu, cpu, uri="",
                  ignore_status=False, print_info=False):
    """
    Changes the cpu affinity for respective vcpu.
    """

    try:
        cmd_vcpupin = "vcpupin %s %s %s" % (domname, vcpu, cpu)
        virsh_cmd(cmd_vcpupin, uri, ignore_status, print_info)

    except error.CmdError, detail:
        logging.error("Virsh vcpupin VM %s failed:\n%s", domname, detail)
        return False


def virsh_vcpuinfo(domname, uri="", ignore_status=False, print_info=False):
    """
    Prints the vcpuinfo of a given domain.
    """

    cmd_vcpuinfo = "vcpuinfo %s" % domname
    return virsh_cmd(cmd_vcpuinfo, uri, ignore_status, print_info).stdout.strip()


def virsh_vcpucount_live(domname, uri="", ignore_status=False, print_info=False):
    """
    Prints the vcpucount of a given domain.
    """

    cmd_vcpucount = "vcpucount --live --active %s" % domname
    return virsh_cmd(cmd_vcpucount, uri, ignore_status, print_info).stdout.strip()


def virsh_freecell(uri = "", ignore_status=False, extra = ""):
    """
    Prints the available amount of memory on the machine or within a NUMA cell.
    """
    cmd_freecell = "freecell %s" % extra
    return virsh_cmd(cmd_freecell, uri, ignore_status)


def virsh_nodeinfo(uri = "", ignore_status=False, extra = ""):
    """
    Returns basic information about the node,like number and type of CPU,
    and size of the physical memory.
    """
    cmd_nodeinfo = "nodeinfo %s" % extra
    return virsh_cmd(cmd_nodeinfo, uri, ignore_status)


def virsh_uri(uri=""):
    """
    Return the hypervisor canonical URI.
    """
    return virsh_cmd("uri", uri).stdout.strip()


def virsh_hostname(uri=""):
    """
    Return the hypervisor hostname.
    """
    return virsh_cmd("hostname", uri).stdout.strip()


def virsh_version(uri=""):
    """
    Return the major version info about what this built from.
    """
    return virsh_cmd("version", uri).stdout.strip()


def virsh_driver(uri=""):
    """
    return the driver by asking libvirt
    """
    # libvirt schme composed of driver + command
    # ref: http://libvirt.org/uri.html
    scheme = urlparse.urlsplit(virsh_uri(uri))[0]
    # extract just the driver, whether or not there is a '+'
    return scheme.split('+', 2)[0]


def virsh_domstate(name, uri=""):
    """
    Return the state about a running domain.

    @param name: VM name
    """
    return virsh_cmd("domstate %s" % name, uri).stdout.strip()


def virsh_domid(name, uri=""):
    """
    Return VM's ID.
    """
    return virsh_cmd("domid %s" % (name), uri).stdout.strip()


def virsh_dominfo(name, uri=""):
    """
    Return the VM information.
    """
    return virsh_cmd("dominfo %s" % (name), uri).stdout.strip()


def virsh_uuid(name, uri=""):
    """
    Return the Converted domain name or id to the domain UUID.

    @param name: VM name
    """
    return virsh_cmd("domuuid %s" % name, uri).stdout.strip()


def virsh_screenshot(name, filename, uri=""):
    try:
        virsh_cmd("screenshot %s %s" % (name, filename), uri)
    except error.CmdError, detail:
        logging.error("Error taking VM %s screenshot. You might have to set "
                      "take_regular_screendumps=no on your tests.cfg config "
                      "file \n%s", name, detail)
    return filename


def virsh_dumpxml(name, to_file="", uri="", ignore_status=False, print_info=False):
    """
    Return the domain information as an XML dump.

    @param name: VM name
    """
    if to_file:
        cmd = "dumpxml %s > %s" % (name, to_file)
    else:
        cmd = "dumpxml %s" % name

    return virsh_cmd(cmd, uri, ignore_status, print_info).stdout.strip()


def virsh_is_alive(name, uri=""):
    """
    Return True if the domain is started/alive.

    @param name: VM name
    """
    return not virsh_is_dead(name, uri)


def virsh_is_dead(name, uri=""):
    """
    Return True if the domain is undefined or not started/dead.

    @param name: VM name
    """
    try:
        state = virsh_domstate(name, uri)
    except error.CmdError:
        return True
    if state in ('running', 'idle', 'no state', 'paused'):
        return False
    else:
        return True


def virsh_suspend(name, uri=""):
    """
    Return True on successful domain suspention of VM.

    Suspend  a domain. It is kept in memory but will not be scheduled.

    @param name: VM name
    """
    try:
        virsh_cmd("suspend %s" % (name), uri)
        if virsh_domstate(name, uri) == 'paused':
            logging.debug("Suspended VM %s", name)
            return True
        else:
            return False
    except error.CmdError, detail:
        logging.error("Suspending VM %s failed:\n%s", name, detail)
        return False


def virsh_resume(name, uri=""):
    """
    Return True on successful domain resumption of VM.

    Move a domain out of the suspended state.

    @param name: VM name
    """
    try:
        virsh_cmd("resume %s" % (name), uri)
        if virsh_is_alive(name, uri):
            logging.debug("Resumed VM %s", name)
            return True
        else:
            return False
    except error.CmdError, detail:
        logging.error("Resume VM %s failed:\n%s", name, detail)
        return False


def virsh_save(name, path, uri=""):
    """
    Store state of VM into named file.

    @param: name: VM Name to operate on
    @param: uri: URI of libvirt hypervisor to use
    @param: path: absolute path to state file
    """
    state = virsh_domstate(name, uri)
    if state not in ('paused',):
        raise virt_vm.VMStatusError("Cannot save a VM that is %s" % state)
    logging.debug("Saving VM %s to %s" %(name, path))
    virsh_cmd("save %s %s" % (name, path), uri)
    # libvirt always stops VM after saving
    state = virsh_domstate(name, uri)
    if state not in ('shut off',):
        raise virt_vm.VMStatusError("VM not shut off after save")


def virsh_restore(name, path, uri=""):
    """
    Load state of VM from named file and remove file.

    @param: name: VM Name to operate on
    @param: uri: URI of libvirt hypervisor to use
    @param: path: absolute path to state file.
    """
    # Blindly assume named VM cooresponds with state in path
    # rely on higher-layers to take exception if missmatch
    state = virsh_domstate(name, uri)
    if state not in ('shut off',):
        raise virt_vm.VMStatusError("Can not restore VM that is %s" % state)
    logging.debug("Restoring VM from %s" % path)
    virsh_cmd("restore %s" % path, uri)
    state = virsh_domstate(name, uri)
    if state not in ('paused','running'):
        raise virt_vm.VMStatusError("VM not paused after restore, it is %s." %
                state)


def virsh_start(name, uri=""):
    """
    Return True on successful domain start.

    Start a (previously defined) inactive domain.

    @param name: VM name
    """
    if virsh_is_alive(name, uri):
        return True
    try:
        virsh_cmd("start %s" % (name), uri)
        return True
    except error.CmdError, detail:
        logging.error("Start VM %s failed:\n%s", name, detail)
        return False


def virsh_shutdown(name, uri=""):
    """
    Return True on successful domain shutdown.

    Gracefully shuts down a domain.

    @param name: VM name
    """
    if virsh_domstate(name, uri) == 'shut off':
        return True
    try:
        virsh_cmd("shutdown %s" % (name), uri)
        return True
    except error.CmdError, detail:
        logging.error("Shutdown VM %s failed:\n%s", name, detail)
        return False


def virsh_destroy(name, uri=""):
    """
    Return True on successful domain destroy.

    Immediately terminate the domain domain-id. The equivalent of ripping
    the power cord out on a physical machine.

    @param name: VM name
    """
    if virsh_domstate(name, uri) == 'shut off':
        return True
    try:
        virsh_cmd("destroy %s" % (name), uri)
        return True
    except error.CmdError, detail:
        logging.error("Destroy VM %s failed:\n%s", name, detail)
        return False


def virsh_define(xml_path, uri=""):
    """
    Return True on successful domain define.

    @param xml_path: XML file path
    """
    try:
        virsh_cmd("define --file %s" % xml_path, uri)
        return True
    except error.CmdError:
        logging.error("Define %s failed.", xml_path)
        return False


def virsh_undefine(name, uri=""):
    """
    Return True on successful domain undefine.

    Undefine the configuration for an inactive domain. The domain should
    be shutdown or destroyed before calling this method.

    @param name: VM name
    """
    try:
        virsh_cmd("undefine %s" % (name), uri)
        logging.debug("undefined VM %s", name)
        return True
    except error.CmdError, detail:
        logging.error("undefine VM %s failed:\n%s", name, detail)
        return False


def virsh_remove_domain(name, uri=""):
    """
    Return True after forcefully removing a domain if it exists.

    @param name: VM name
    """
    if virsh_domain_exists(name, uri):
        if virsh_is_alive(name, uri):
            virsh_destroy(name, uri)
        virsh_undefine(name, uri)
    return True


def virsh_domain_exists(name, uri=""):
    """
    Return True if a domain exits.

    @param name: VM name
    """
    try:
        virsh_cmd("domstate %s" % name, uri)
        return True
    except error.CmdError, detail:
        logging.warning("VM %s does not exist:\n%s", name, detail)
        return False


def virsh_migrate(name="", dest_uri="", option="", extra="", uri="",
                  ignore_status=False, print_info=False):
    """
    Migrate a guest to another host.

    @param: name: name of guest on uri
    @param: dest_uri: libvirt uri to send guest to
    @param: option: Free-form string of options to virsh migrate
    @param: extra: Free-form string of options to follow <domain> <desturi>
    @param: ignore_status: virsh_cmd() raises an exception when error if False
    @param: print_info: virsh_cmd() print status, stdout and stderr if True
    @return: True if migration command was successful
    """
    cmd = "migrate"
    if option:
        cmd += " %s" % option
    if name:
        cmd += " --domain %s" % name
    if dest_uri:
        cmd += " --desturi %s" % dest_uri
    if extra:
        cmd += " %s" % extra

    return virsh_cmd(cmd, uri, ignore_status, print_info)


def virsh_attach_device(name, xml_file, extra="", uri=""):
    """
    Attach a device to VM.
    """
    cmd = "attach-device --domain %s --file %s %s" % (name, xml_file, extra)
    try:
        virsh_cmd(cmd, uri)
        return True
    except error.CmdError:
        logging.error("Attaching device to VM %s failed." % name)
        return False


def virsh_detach_device(name, xml_file, extra="", uri=""):
    """
    Detach a device from VM.
    """
    cmd = "detach-device --domain %s --file %s %s" % (name, xml_file, extra)
    try:
        virsh_cmd(cmd, uri)
        return True
    except error.CmdError:
        logging.error("Detaching device from VM %s failed." % name)
        return False


def virsh_attach_interface(name, option="", uri="", ignore_status=False, print_info=False):
    """
    Attach a NIC to VM.
    """
    cmd = "attach-interface "

    if name:
        cmd += "--domain %s" % name
    if option:
        cmd += " %s" % option

    return virsh_cmd(cmd, uri, ignore_status, print_info)


def virsh_detach_interface(name, option="", uri="", ignore_status=False, print_info=False):
    """
    Detach a NIC to VM.
    """
    cmd = "detach-interface "

    if name:
        cmd += "--domain %s" % name
    if option:
        cmd += " %s" % option

    return virsh_cmd(cmd, uri, ignore_status, print_info)


def virsh_net_create(xml_file, extra="", uri="",
                     ignore_status=False, print_info=False):
    """
    Create network from a XML file.
    """
    cmd = "net-create --file %s %s" % (xml_file, extra)
    return virsh_cmd(cmd, uri, ignore_status, print_info)


def virsh_net_list(options, extra="", uri="",
                   ignore_status=False, print_info=False):
    """
    List networks on host.
    """
    cmd = "net-list %s %s" % (options, extra)
    return virsh_cmd(cmd, uri, ignore_status, print_info)


def virsh_net_destroy(name, extra="", uri="",
                      ignore_status=False, print_info=False):
    """
    Destroy actived network on host.
    """
    cmd = "net-destroy --network %s %s" % (name, extra)
    return virsh_cmd(cmd, uri, ignore_status, print_info)


def virsh_pool_info(name, uri=""):
    """
    Returns basic information about the storage pool.
    """
    cmd = "pool-info %s" % name
    try:
        virsh_cmd(cmd, uri)
        return True
    except error.CmdError, detail:
        logging.error("Pool %s doesn't exist:\n%s", name, detail)
        return False


def virsh_pool_destroy(name, uri=""):
    """
    Forcefully stop a given pool.
    """
    cmd = "pool-destroy %s" % name
    try:
        virsh_cmd(cmd, uri)
        return True
    except error.CmdError, detail:
        logging.error("Failed to destroy pool: %s." % detail)
        return False


def virsh_pool_create_as(name, _type, target, extra="", uri=""):
    """
    Create a pool from a set of args.

    @param: name: name of pool
    @param: type: storage pool type such as 'dir'
    @param: target: libvirt uri to send guest to
    @param: extra: Free-form string of options
    @return: True if pool creation command was successful
    """

    if not name:
        logging.error("Please give a pool name")

    types = [ 'dir', 'fs', 'netfs', 'disk', 'iscsi', 'logical' ]

    if _type and _type not in types:
        logging.error("Only support pool types: %s." % types)
    elif not _type:
        _type = types[0]

    logging.info("Create %s type pool %s" % (_type, name))
    cmd = "pool-create-as --name %s --type %s --target %s %s" \
          % (name, _type, target, extra)
    try:
        virsh_cmd(cmd, uri)
        return True
    except error.CmdError, detail:
        logging.error("Failed to create pool: %s." % detail)
        return False


class VM(virt_vm.BaseVM):
    """
    This class handles all basic VM operations for libvirt.
    """

    def __init__(self, name, params, root_dir, address_cache, state=None):
        """
        Initialize the object and set a few attributes.

        @param name: The name of the object
        @param params: A dict containing VM params
                (see method __make_libvirt_command for a full description)
        @param root_dir: Base directory for relative filenames
        @param address_cache: A dict that maps MAC addresses to IP addresses
        @param state: If provided, use this as self.__dict__
        """

        if state:
            self.__dict__ = state
        else:
            self.process = None
            self.serial_console = None
            self.redirs = {}
            self.vnc_port = None
            self.vnc_autoport = True
            self.pci_assignable = None
            self.netdev_id = []
            self.device_id = []
            self.pci_devices = []
            self.uuid = None
            self.only_pty = False

        self.spice_port = 8000
        self.name = name
        self.params = params
        self.root_dir = root_dir
        self.address_cache = address_cache
        self.vnclisten = "0.0.0.0"
        self.connect_uri = params.get("connect_uri", "default")
        if self.connect_uri == 'default':
            self.connect_uri = virsh_uri()
        else: # Validate and canonicalize uri early to catch problems
            self.connect_uri = virsh_uri(uri = self.connect_uri)
        self.driver_type = virsh_driver(uri = self.connect_uri)
        self.params['driver_type_'+self.name] = self.driver_type
        # virtnet init depends on vm_type/driver_type being set w/in params
        super(VM, self).__init__(name, params)
        logging.info("Libvirt VM '%s', driver '%s', uri '%s'",
                     self.name, self.driver_type, self.connect_uri)


    def verify_alive(self):
        """
        Make sure the VM is alive.

        @raise VMDeadError: If the VM is dead
        """
        if not self.is_alive():
            raise virt_vm.VMDeadError("Domain %s is inactive" % self.name,
                                      virsh_domstate(self.name, self.connect_uri))


    def is_alive(self):
        """
        Return True if VM is alive.
        """
        return virsh_is_alive(self.name, self.connect_uri)


    def is_dead(self):
        """
        Return True if VM is dead.
        """
        return virsh_is_dead(self.name, self.connect_uri)


    def is_persistent(self):
        """
        Return True if VM is persistent.
        """
        try:
            return bool(re.search(r"^Persistent:\s+[Yy]es",
                        virsh_dominfo(self.name, self.connect_uri),
                        re.MULTILINE))
        except error.CmdError:
            return False

    def undefine(self):
        """
        Undefine the VM.
        """
        return virsh_undefine(self.name, self.connect_uri)


    def define(self, xml_file):
        """
        Define the VM.
        """
        if not os.path.exists(xml_file):
            logging.error("File %s not found." % xml_file)
            return False
        return virsh_define(xml_file, self.connect_uri)


    def state(self):
        """
        Return domain state.
        """
        return virsh_domstate(self.name, self.connect_uri)


    def get_id(self):
        """
        Return VM's ID.
        """
        return virsh_domid(self.name, self.connect_uri)


    def get_xml(self):
        """
        Return VM's xml file.
        """
        return virsh_dumpxml(self.name, uri=self.connect_uri)


    def backup_xml(self):
        """
        Backup the guest's xmlfile.
        """
        # Since backup_xml() is not a function for testing,
        # we have to handle the exception here.
        try:
            xml_file = tempfile.mktemp(dir="/tmp")

            virsh_dumpxml(self.name, to_file=xml_file, uri=self.connect_uri)
            return xml_file
        except Exception, detail:
            if os.path.exists(xml_file):
                os.remove(xml_file)
            logging.error("Failed to backup xml file:\n%s", detail)
            return ""


    def clone(self, name=None, params=None, root_dir=None, address_cache=None,
              copy_state=False):
        """
        Return a clone of the VM object with optionally modified parameters.
        The clone is initially not alive and needs to be started using create().
        Any parameters not passed to this function are copied from the source
        VM.

        @param name: Optional new VM name
        @param params: Optional new VM creation parameters
        @param root_dir: Optional new base directory for relative filenames
        @param address_cache: A dict that maps MAC addresses to IP addresses
        @param copy_state: If True, copy the original VM's state to the clone.
                Mainly useful for __make_libvirt_command().
        """
        if name is None:
            name = self.name
        if params is None:
            params = self.params.copy()
        if root_dir is None:
            root_dir = self.root_dir
        if address_cache is None:
            address_cache = self.address_cache
        if copy_state:
            state = self.__dict__.copy()
        else:
            state = None
        return VM(name, params, root_dir, address_cache, state)


    def __make_libvirt_command(self, name=None, params=None, root_dir=None):
        """
        Generate a libvirt command line. All parameters are optional. If a
        parameter is not supplied, the corresponding value stored in the
        class attributes is used.

        @param name: The name of the object
        @param params: A dict containing VM params
        @param root_dir: Base directory for relative filenames

        @note: The params dict should contain:
               mem -- memory size in MBs
               cdrom -- ISO filename to use with the qemu -cdrom parameter
               extra_params -- a string to append to the qemu command
               shell_port -- port of the remote shell daemon on the guest
               (SSH, Telnet or the home-made Remote Shell Server)
               shell_client -- client program to use for connecting to the
               remote shell daemon on the guest (ssh, telnet or nc)
               x11_display -- if specified, the DISPLAY environment variable
               will be be set to this value for the qemu process (useful for
               SDL rendering)
               images -- a list of image object names, separated by spaces
               nics -- a list of NIC object names, separated by spaces

               For each image in images:
               drive_format -- string to pass as 'if' parameter for this
               image (e.g. ide, scsi)
               image_snapshot -- if yes, pass 'snapshot=on' to qemu for
               this image
               image_boot -- if yes, pass 'boot=on' to qemu for this image
               In addition, all parameters required by get_image_filename.

               For each NIC in nics:
               nic_model -- string to pass as 'model' parameter for this
               NIC (e.g. e1000)
        """
        # helper function for command line option wrappers
        def has_option(help, option):
            return bool(re.search(r"--%s" % option, help, re.MULTILINE))

        # Wrappers for all supported libvirt command line parameters.
        # This is meant to allow support for multiple libvirt versions.
        # Each of these functions receives the output of 'libvirt --help' as a
        # parameter, and should add the requested command line option
        # accordingly.

        def add_name(help, name):
            return " --name '%s'" % name

        def add_machine_type(help, machine_type):
            if has_option(help, "machine"):
                return " --machine %s" % machine_type
            else:
                return ""

        def add_hvm_or_pv(help, hvm_or_pv):
            if hvm_or_pv == "hvm":
                return " --hvm --accelerate"
            elif hvm_or_pv == "pv":
                return " --paravirt"
            else:
                logging.warning("Unknown virt type hvm_or_pv, using default.")
                return ""

        def add_mem(help, mem):
            return " --ram=%s" % mem

        def add_check_cpu(help):
            if has_option(help, "check-cpu"):
                return " --check-cpu"
            else:
                return ""

        def add_smp(help, smp):
            return " --vcpu=%s" % smp

        def add_location(help, location):
            if has_option(help, "location"):
                return " --location %s" % location
            else:
                return ""

        def add_cdrom(help, filename, index=None):
            if has_option(help, "cdrom"):
                return " --cdrom %s" % filename
            else:
                return ""

        def add_pxe(help):
            if has_option(help, "pxe"):
                return " --pxe"
            else:
                return ""

        def add_import(help):
            if has_option(help, "import"):
                return " --import"
            else:
                return ""

        def add_drive(help, filename, pool=None, vol=None, device=None,
                      bus=None, perms=None, size=None, sparse=False,
                      cache=None, format=None):
            cmd = " --disk"
            if filename:
                cmd += " path=%s" % filename
            elif pool:
                if vol:
                    cmd += " vol=%s/%s" % (pool, vol)
                else:
                    cmd += " pool=%s" % pool
            if device:
                cmd += ",device=%s" % device
            if bus:
                cmd += ",bus=%s" % bus
            if perms:
                cmd += ",%s" % perms
            if size:
                cmd += ",size=%s" % size.rstrip("Gg")
            if sparse:
                cmd += ",sparse=false"
            if format:
                cmd += ",format=%s" % format
            if cache:
                cmd += ",cache=%s" % cache
            return cmd

        def add_floppy(help, filename):
            return " --disk path=%s,device=floppy,ro" % filename

        def add_vnc(help, vnc_port=None):
            if vnc_port:
                return " --vnc --vncport=%d" % (vnc_port)
            else:
                return " --vnc"

        def add_vnclisten(help, vnclisten):
            if has_option(help, "vnclisten"):
                return " --vnclisten=%s" % (vnclisten)
            else:
                return ""

        def add_sdl(help):
            if has_option(help, "sdl"):
                return " --sdl"
            else:
                return ""

        def add_nographic(help):
            return " --nographics"

        def add_video(help, video_device):
            if has_option(help, "video"):
                return " --video=%s" % (video_device)
            else:
                return ""

        def add_uuid(help, uuid):
            if has_option(help, "uuid"):
                return " --uuid %s" % uuid
            else:
                return ""

        def add_os_type(help, os_type):
            if has_option(help, "os-type"):
                return " --os-type %s" % os_type
            else:
                return ""

        def add_os_variant(help, os_variant):
            if has_option(help, "os-variant"):
                return " --os-variant %s" % os_variant
            else:
                return ""

        def add_pcidevice(help, pci_device):
            if has_option(help, "host-device"):
                return " --host-device %s" % pci_device
            else:
                return ""

        def add_soundhw(help, sound_device):
            if has_option(help, "soundhw"):
                return " --soundhw %s" % sound_device
            else:
                return ""

        def add_serial(help, filename):
            if has_option(help, "serial"):
                return "  --serial file,path=%s --serial pty" % filename
            else:
                self.only_pty = True
                return ""

        def add_kernel_cmdline(help, cmdline):
            return " -append %s" % cmdline

        def add_connect_uri(help, uri):
            if has_option(help, "connect"):
                return " --connect=%s" % uri
            else:
                return ""

        def add_nic(help, nic_params):
            """
            Return additional command line params based on dict-like nic_params
            """
            mac = nic_params.get('mac')
            nettype = nic_params.get('nettype')
            netdst = nic_params.get('netdst')
            nic_model = nic_params.get('nic_model')
            if nettype:
                result = " --network=%s" % nettype
            else:
                result = ""
            if has_option(help, "bridge"):
                # older libvirt (--network=NATdev --bridge=bridgename --mac=mac)
                if nettype != 'user':
                    result += ':%s' % netdst
                if mac: # possible to specify --mac w/o --network
                    result += " --mac=%s" % mac
            else:
                # newer libvirt (--network=mynet,model=virtio,mac=00:11)
                if nettype != 'user':
                    result += '=%s' % netdst
                if nettype and nic_model: # only supported along with nettype
                    result += ",model=%s" % nic_model
                if nettype and mac:
                    result += ',mac=%s' % mac
                elif mac: # possible to specify --mac w/o --network
                    result += " --mac=%s" % mac
            logging.debug("vm.__make_libvirt_command.add_nic returning: %s"
                             % result)
            return result

        # End of command line option wrappers

        if name is None:
            name = self.name
        if params is None:
            params = self.params
        if root_dir is None:
            root_dir = self.root_dir

        # Clone this VM using the new params
        vm = self.clone(name, params, root_dir, copy_state=True)

        virt_install_binary = virt_utils.get_path(
            root_dir,
            params.get("virt_install_binary",
                       "virt-install"))

        help = utils.system_output("%s --help" % virt_install_binary)

        # Start constructing the qemu command
        virt_install_cmd = ""
        # Set the X11 display parameter if requested
        if params.get("x11_display"):
            virt_install_cmd += "DISPLAY=%s " % params.get("x11_display")
        # Add the qemu binary
        virt_install_cmd += virt_install_binary

        # set connect uri
        virt_install_cmd += add_connect_uri(help, self.connect_uri)

        # hvm or pv specificed by libvirt switch (pv used  by Xen only)
        hvm_or_pv = params.get("hvm_or_pv", "hvm")
        if hvm_or_pv:
            virt_install_cmd += add_hvm_or_pv(help, hvm_or_pv)

        # Add the VM's name
        virt_install_cmd += add_name(help, name)

        machine_type = params.get("machine_type")
        if machine_type:
            virt_install_cmd += add_machine_type(help, machine_type)

        mem = params.get("mem")
        if mem:
            virt_install_cmd += add_mem(help, mem)

        # TODO: should we do the check before we call ? negative case ?
        check_cpu = params.get("use_check_cpu")
        if check_cpu:
            virt_install_cmd += add_check_cpu(help)

        smp = params.get("smp")
        if smp:
            virt_install_cmd += add_smp(help, smp)

        # TODO: directory location for vmlinuz/kernel for cdrom install ?
        location = None
        if params.get("medium") == 'url':
            location = params.get('url')

        elif params.get("medium") == 'kernel_initrd':
            # directory location of kernel/initrd pair (directory layout must
            # be in format libvirt will recognize)
            location = params.get("image_dir")

        elif params.get("medium") == 'nfs':
            location = "nfs:%s:%s" % (params.get("nfs_server"),
                                      params.get("nfs_dir"))

        elif params.get("medium") == 'cdrom':
            if params.get("use_libvirt_cdrom_switch") == 'yes':
                virt_install_cmd += add_cdrom(help, params.get("cdrom_cd1"))
            elif params.get("unattended_delivery_method") == "integrated":
                virt_install_cmd += add_cdrom(help,
                                              params.get("cdrom_unattended"))
            else:
                location = params.get("image_dir")
                kernel_dir = os.path.dirname(params.get("kernel"))
                kernel_parent_dir = os.path.dirname(kernel_dir)
                pxeboot_link = os.path.join(kernel_parent_dir, "pxeboot")
                if os.path.islink(pxeboot_link):
                    os.unlink(pxeboot_link)
                if os.path.isdir(pxeboot_link):
                    logging.info("Removed old %s leftover directory",
                                 pxeboot_link)
                    shutil.rmtree(pxeboot_link)
                os.symlink(kernel_dir, pxeboot_link)

        elif params.get("medium") == "import":
            virt_install_cmd += add_import(help)

        if location:
            virt_install_cmd += add_location(help, location)

        if params.get("display") == "vnc":
            if params.get("vnc_autoport") == "yes":
                vm.vnc_autoport = True
            else:
                vm.vnc_autoport = False
            if not vm.vnc_autoport and params.get("vnc_port"):
                vm.vnc_port = int(params.get("vnc_port"))
            virt_install_cmd += add_vnc(help, vm.vnc_port)
            if params.get("vnclisten"):
                vm.vnclisten = params.get("vnclisten")
            virt_install_cmd += add_vnclisten(help, vm.vnclisten)
        elif params.get("display") == "sdl":
            virt_install_cmd += add_sdl(help)
        elif params.get("display") == "nographic":
            virt_install_cmd += add_nographic(help)

        video_device = params.get("video_device")
        if video_device:
            virt_install_cmd += add_video(help, video_device)

        sound_device = params.get("sound_device")
        if sound_device:
            virt_install_cmd += add_soundhw(help, sound_device)

        # if none is given a random UUID will be generated by libvirt
        if params.get("uuid"):
            virt_install_cmd += add_uuid(help, params.get("uuid"))

        # selectable OS type
        if params.get("use_os_type") == "yes":
            virt_install_cmd += add_os_type(help, params.get("os_type"))

        # selectable OS variant
        if params.get("use_os_variant") == "yes":
            virt_install_cmd += add_os_variant(help, params.get("os_variant"))

        # Add serial console
        virt_install_cmd += add_serial(help, self.get_serial_console_filename())

        # If the PCI assignment step went OK, add each one of the PCI assigned
        # devices to the command line.
        if self.pci_devices:
            for pci_id in self.pci_devices:
                virt_install_cmd += add_pcidevice(help, pci_id)

        for image_name in params.objects("images"):
            image_params = params.object_params(image_name)
            filename = virt_storage.get_image_filename(image_params, root_dir)
            if image_params.get("use_storage_pool") == "yes":
                filename = None
                virt_install_cmd += add_drive(help,
                                  filename,
                                  image_params.get("image_pool"),
                                  image_params.get("image_vol"),
                                  image_params.get("image_device"),
                                  image_params.get("image_bus"),
                                  image_params.get("image_perms"),
                                  image_params.get("image_size"),
                                  image_params.get("drive_sparse"),
                                  image_params.get("drive_cache"),
                                  image_params.get("image_format"))

            if image_params.get("boot_drive") == "no":
                continue
            if filename:
                virt_install_cmd += add_drive(help,
                                    filename,
                                    None,
                                    None,
                                    None,
                                    image_params.get("drive_format"),
                                    None,
                                    image_params.get("image_size"),
                                    image_params.get("drive_sparse"),
                                    image_params.get("drive_cache"),
                                    image_params.get("image_format"))

        if (params.get('unattended_delivery_method') != 'integrated' and
            not (self.driver_type == 'xen' and params.get('hvm_or_pv') == 'pv')):
            for cdrom in params.objects("cdroms"):
                cdrom_params = params.object_params(cdrom)
                iso = cdrom_params.get("cdrom")
                if params.get("use_libvirt_cdrom_switch") == 'yes':
                    # we don't want to skip the winutils iso
                    if not cdrom == 'winutils':
                        logging.debug("Using --cdrom instead of --disk for install")
                        logging.debug("Skipping CDROM:%s:%s", cdrom, iso)
                        continue
                if params.get("medium") == 'cdrom_no_kernel_initrd':
                    if iso == params.get("cdrom_cd1"):
                        logging.debug("Using cdrom or url for install")
                        logging.debug("Skipping CDROM: %s", iso)
                        continue

                if iso:
                    virt_install_cmd += add_drive(help,
                                 virt_utils.get_path(root_dir, iso),
                                      image_params.get("iso_image_pool"),
                                      image_params.get("iso_image_vol"),
                                      'cdrom',
                                      None,
                                      None,
                                      None,
                                      None,
                                      None,
                                      None)

        # We may want to add {floppy_otps} parameter for -fda
        # {fat:floppy:}/path/. However vvfat is not usually recommended.
        # Only support to add the main floppy if you want to add the second
        # one please modify this part.
        floppy = params.get("floppy_name")
        if floppy:
            floppy = virt_utils.get_path(root_dir, floppy)
            virt_install_cmd += add_drive(help, floppy,
                              None,
                              None,
                              'floppy',
                              None,
                              None,
                              None,
                              None,
                              None,
                              None)

        # setup networking parameters
        for nic in vm.virtnet:
            # __make_libvirt_command can be called w/o vm.create()
            nic = vm.add_nic(**dict(nic))
            logging.debug("__make_libvirt_command() setting up command for"
                          " nic: %s" % str(nic))
            virt_install_cmd += add_nic(help,nic)

        if params.get("use_no_reboot") == "yes":
            virt_install_cmd += " --noreboot"

        if params.get("use_autostart") == "yes":
            virt_install_cmd += " --autostart"

        if params.get("virt_install_debug") == "yes":
            virt_install_cmd += " --debug"

        # bz still open, not fully functional yet
        if params.get("use_virt_install_wait") == "yes":
            virt_install_cmd += (" --wait %s" %
                                 params.get("virt_install_wait_time"))

        kernel_params = params.get("kernel_params")
        if kernel_params:
            virt_install_cmd += " --extra-args '%s'" % kernel_params

        virt_install_cmd += " --noautoconsole"

        return virt_install_cmd


    @error.context_aware
    def create(self, name=None, params=None, root_dir=None, timeout=5.0,
               migration_mode=None, mac_source=None):
        """
        Start the VM by running a qemu command.
        All parameters are optional. If name, params or root_dir are not
        supplied, the respective values stored as class attributes are used.

        @param name: The name of the object
        @param params: A dict containing VM params
        @param root_dir: Base directory for relative filenames
        @param migration_mode: If supplied, start VM for incoming migration
                using this protocol (either 'tcp', 'unix' or 'exec')
        @param migration_exec_cmd: Command to embed in '-incoming "exec: ..."'
                (e.g. 'gzip -c -d filename') if migration_mode is 'exec'
        @param mac_source: A VM object from which to copy MAC addresses. If not
                specified, new addresses will be generated.

        @raise VMCreateError: If qemu terminates unexpectedly
        @raise VMKVMInitError: If KVM initialization fails
        @raise VMHugePageError: If hugepage initialization fails
        @raise VMImageMissingError: If a CD image is missing
        @raise VMHashMismatchError: If a CD image hash has doesn't match the
                expected hash
        @raise VMBadPATypeError: If an unsupported PCI assignment type is
                requested
        @raise VMPAError: If no PCI assignable devices could be assigned
        """
        error.context("creating '%s'" % self.name)
        self.destroy(free_mac_addresses=False)

        if name is not None:
            self.name = name
        if params is not None:
            self.params = params
        if root_dir is not None:
            self.root_dir = root_dir
        name = self.name
        params = self.params
        root_dir = self.root_dir

        # Verify the md5sum of the ISO images
        for cdrom in params.objects("cdroms"):
            if params.get("medium") == "import":
                break
            cdrom_params = params.object_params(cdrom)
            iso = cdrom_params.get("cdrom")
            if ((self.driver_type == 'xen') and
                (params.get('hvm_or_pv') == 'pv') and
                (os.path.basename(iso) == 'ks.iso')):
                continue
            if iso:
                iso = virt_utils.get_path(root_dir, iso)
                if not os.path.exists(iso):
                    raise virt_vm.VMImageMissingError(iso)
                compare = False
                if cdrom_params.get("md5sum_1m"):
                    logging.debug("Comparing expected MD5 sum with MD5 sum of "
                                  "first MB of ISO file...")
                    actual_hash = utils.hash_file(iso, 1048576, method="md5")
                    expected_hash = cdrom_params.get("md5sum_1m")
                    compare = True
                elif cdrom_params.get("md5sum"):
                    logging.debug("Comparing expected MD5 sum with MD5 sum of "
                                  "ISO file...")
                    actual_hash = utils.hash_file(iso, method="md5")
                    expected_hash = cdrom_params.get("md5sum")
                    compare = True
                elif cdrom_params.get("sha1sum"):
                    logging.debug("Comparing expected SHA1 sum with SHA1 sum "
                                  "of ISO file...")
                    actual_hash = utils.hash_file(iso, method="sha1")
                    expected_hash = cdrom_params.get("sha1sum")
                    compare = True
                if compare:
                    if actual_hash == expected_hash:
                        logging.debug("Hashes match")
                    else:
                        raise virt_vm.VMHashMismatchError(actual_hash,
                                                          expected_hash)

        # Make sure the following code is not executed by more than one thread
        # at the same time
        lockfile = open("/tmp/libvirt-autotest-vm-create.lock", "w+")
        fcntl.lockf(lockfile, fcntl.LOCK_EX)

        try:
            # Handle port redirections
            redir_names = params.objects("redirs")
            host_ports = virt_utils.find_free_ports(5000, 6000, len(redir_names))
            self.redirs = {}
            for i in range(len(redir_names)):
                redir_params = params.object_params(redir_names[i])
                guest_port = int(redir_params.get("guest_port"))
                self.redirs[guest_port] = host_ports[i]

            # Find available PCI devices
            self.pci_devices = []
            for device in params.objects("pci_devices"):
                self.pci_devices.append(device)

            # Find available VNC port, if needed
            if params.get("display") == "vnc":
                if params.get("vnc_autoport") == "yes":
                    self.vnc_port = None
                    self.vnc_autoport = True
                else:
                    self.vnc_port = virt_utils.find_free_port(5900, 6100)
                    self.vnc_autoport = False

            # Find available spice port, if needed
            if params.get("spice"):
                self.spice_port = virt_utils.find_free_port(8000, 8100)

            # Find random UUID if specified 'uuid = random' in config file
            if params.get("uuid") == "random":
                f = open("/proc/sys/kernel/random/uuid")
                self.uuid = f.read().strip()
                f.close()

            # Generate or copy MAC addresses for all NICs
            for nic in self.virtnet:
                nic_params = dict(nic)
                if mac_source:
                    # Will raise exception if source doesn't
                    # have cooresponding nic
                    logging.debug("Copying mac for nic %s from VM %s"
                                    % (nic.nic_name, mac_source.nam))
                    nic_params['mac'] = mac_source.get_mac_address(nic.nic_name)
                # __make_libvirt_command() calls vm.add_nic (i.e. on a copy)
                nic = self.add_nic(**nic_params)
                logging.debug('VM.create activating nic %s' % nic)
                self.activate_nic(nic.nic_name)

            # Make qemu command
            install_command = self.__make_libvirt_command()

            logging.info("Running libvirt command:\n%s", install_command)
            utils.run(install_command, verbose=False)
            # Wait for the domain to be created
            virt_utils.wait_for(func=self.is_alive, timeout=60,
                                text=("waiting for domain %s to start" %
                                      self.name))
            self.uuid = virsh_uuid(self.name, self.connect_uri)

            # Establish a session with the serial console
            if self.only_pty == True:
                self.serial_console = aexpect.ShellSession(
                    "virsh console %s" % self.name,
                    auto_close=False,
                    output_func=virt_utils.log_line,
                    output_params=("serial-%s.log" % name,))
            else:
                self.serial_console = aexpect.ShellSession(
                    "tail -f %s" % self.get_serial_console_filename(),
                    auto_close=False,
                    output_func=virt_utils.log_line,
                    output_params=("serial-%s.log" % name,))

        finally:
            fcntl.lockf(lockfile, fcntl.LOCK_UN)
            lockfile.close()


    def migrate(self, dest_uri="", option="--live --timeout 60", extra="",
                ignore_status=False, print_info=False):
        """
        Migrate a VM to a remote host.

        @param: dest_uri: Destination libvirt URI
        @param: option: Migration options before <domain> <desturi>
        @param: extra: Migration options after <domain> <desturi>
        @return: True if command succeeded
        """
        logging.info("Migrating VM %s from %s to %s" %
                     (self.name, self.connect_uri, dest_uri))
        result = virsh_migrate(self.name, dest_uri, option,
                               extra, self.connect_uri,
                               ignore_status, print_info)
        # On successful migration, point to guests new hypervisor.
        # Since dest_uri could be None, checking it is necessary.
        if result.exit_status == 0 and dest_uri:
            self.connect_uri = dest_uri
        return result


    def attach_device(self, xml_file, extra=""):
        """
        Attach a device to VM.
        """
        return virsh_attach_device(self.name, xml_file, extra, self.connect_uri)


    def detach_device(self, xml_file, extra=""):
        """
        Detach a device from VM.
        """
        return virsh_detach_device(self.name, xml_file, extra, self.connect_uri)


    def attach_interface(self, option="", ignore_status=False, print_info=False):
        """
        Attach a NIC to VM.
        """
        return virsh_attach_interface(self.name, option, self.connect_uri,
                                      ignore_status=ignore_status, print_info=print_info)


    def detach_interface(self, option="", ignore_status=False, print_info=False):
        """
        Detach a NIC to VM.
        """
        return virsh_detach_interface(self.name, option, self.connect_uri,
                                      ignore_status=ignore_status, print_info=print_info)


    def destroy(self, gracefully=True, free_mac_addresses=True):
        """
        Destroy the VM.

        If gracefully is True, first attempt to shutdown the VM with a shell
        command. If that fails, send SIGKILL to the qemu process.

        @param gracefully: If True, an attempt will be made to end the VM
                using a shell command before trying to end the qemu process
                with a 'quit' or a kill signal.
        @param free_mac_addresses: If vm is undefined with libvirt, also
                                   release/reset associated mac address
        """
        try:
            # Is it already dead?
            if self.is_alive():
                logging.debug("Destroying VM")
                if gracefully and self.params.get("shutdown_command"):
                    # Try to destroy with shell command
                    logging.debug("Trying to shutdown VM with shell command")
                    try:
                        session = self.login()
                    except (virt_remote.LoginError, virt_vm.VMError), e:
                        logging.debug(e)
                    else:
                        try:
                            # Send the shutdown command
                            session.sendline(self.params.get("shutdown_command"))
                            logging.debug("Shutdown command sent; waiting for VM "
                                          "to go down...")
                            if virt_utils.wait_for(self.is_dead, 60, 1, 1):
                                logging.debug("VM is down")
                                return
                        finally:
                            session.close()
                virsh_destroy(self.name, self.connect_uri)

        finally:
            if self.serial_console:
                self.serial_console.close()
            for f in ([self.get_testlog_filename(),
                       self.get_serial_console_filename()]):
                try:
                    os.unlink(f)
                except OSError:
                    pass
            if hasattr(self, "migration_file"):
                try:
                    os.unlink(self.migration_file)
                except OSError:
                    pass

        if free_mac_addresses:
            if self.is_persistent():
                logging.warning("Requested MAC address release from "
                                "persistent vm %s. Ignoring." % self.name)
            else:
                logging.debug("Releasing MAC addresses for vm %s." % self.name)
                for nic_name in self.virtnet.nic_name_list():
                    self.virtnet.free_mac_address(nic_name)


    def remove(self):
        self.destroy(gracefully=True, free_mac_addresses=False)
        if not self.undefine():
            raise virt_vm.VMRemoveError("VM '%s' undefine error" % self.name)
        self.destroy(gracefully=False, free_mac_addresses=True)
        logging.debug("VM '%s' was removed", self.name)


    def get_uuid(self):
        """
        Return VM's UUID.
        """
        return virsh_uuid(self.name, self.connect_uri)


    def get_port(self, port, nic_index=0):
        """
        Return the port in host space corresponding to port in guest space.

        @param port: Port number in host space.
        @param nic_index: Index of the NIC.
        @return: If port redirection is used, return the host port redirected
                to guest port port. Otherwise return port.
        @raise VMPortNotRedirectedError: If an unredirected port is requested
                in user mode
        """
        if self.virtnet[nic_index].nettype == "bridge":
            return port
        else:
            try:
                return self.redirs[port]
            except KeyError:
                raise virt_vm.VMPortNotRedirectedError(port)


    def get_ifname(self, nic_index=0):
        raise NotImplementedError

    def get_virsh_mac_address(self, nic_index=0):
        """
        Get the MAC of this VM domain.

        @param nic_index: Index of the NIC
        @raise VMMACAddressMissingError: If no MAC address is defined for the
                requested NIC
        """
        thexml = virsh_dumpxml(self.name, uri=self.connect_uri)
        dom = minidom.parseString(thexml)
        count = 0
        for node in dom.getElementsByTagName('interface'):
            source = node.childNodes[1]
            x = source.attributes["address"]
            if nic_index == count:
                return x.value
            count += 1
        raise virt_vm.VMMACAddressMissingError(nic_index)


    def get_pid(self):
        """
        Return the VM's PID.

        @return: int with PID. If VM is not alive, returns None.
        """
        pid_file = "/var/run/libvirt/qemu/%s.pid" % self.name
        pid = None
        if os.path.exists(pid_file):
            try:
                pid_file_contents = open(pid_file).read()
                pid = int(pid_file_contents)
            except IOError:
                logging.error("Could not read %s to get PID", pid_file)
            except TypeError:
                logging.error("PID file %s has invalid contents: '%s'",
                              pid_file, pid_file_contents)
        else:
            logging.debug("PID file %s not present", pid_file)

        return pid


    def get_vcpus_pid(self):
        """
        Return the vcpu's pid for a given VM.

        @return: list of PID of vcpus of a VM.
        """

        vcpu_pids = []
        output = virsh_qemu_monitor_command(self.name, "info cpus")
        vcpu_pids = re.findall(r'thread_id=(\d+)', output.stdout)
        return vcpu_pids


    def get_shell_pid(self):
        """
        Return the PID of the parent shell process.

        @note: This works under the assumption that self.process.get_pid()
        returns the PID of the parent shell process.
        """
        return self.process.get_pid()


    def get_shared_meminfo(self):
        """
        Returns the VM's shared memory information.

        @return: Shared memory used by VM (MB)
        """
        if self.is_dead():
            logging.error("Could not get shared memory info from dead VM.")
            return None

        filename = "/proc/%d/statm" % self.get_pid()
        shm = int(open(filename).read().split()[2])
        # statm stores informations in pages, translate it to MB
        return shm * 4.0 / 1024

    def activate_nic(self, nic_index_or_name):
        #TODO: Impliment nic hotplugging
        pass # Just a stub for now

    def deactivate_nic(self, nic_index_or_name):
        #TODO: Impliment nic hot un-plugging
        pass # Just a stub for now

    @error.context_aware
    def reboot(self, session=None, method="shell", nic_index=0, timeout=240):
        """
        Reboot the VM and wait for it to come back up by trying to log in until
        timeout expires.

        @param session: A shell session object or None.
        @param method: Reboot method.  Can be "shell" (send a shell reboot
                command).
        @param nic_index: Index of NIC to access in the VM, when logging in
                after rebooting.
        @param timeout: Time to wait for login to succeed (after rebooting).
        @return: A new shell session object.
        """
        error.base_context("rebooting '%s'" % self.name, logging.info)
        error.context("before reboot")
        session = session or self.login()
        error.context()

        if method == "shell":
            session.sendline(self.params.get("reboot_command"))
        else:
            raise virt_vm.VMRebootError("Unknown reboot method: %s" % method)

        error.context("waiting for guest to go down", logging.info)
        if not virt_utils.wait_for(lambda:
                                  not session.is_responsive(timeout=30),
                                  120, 0, 1):
            raise virt_vm.VMRebootError("Guest refuses to go down")
        session.close()

        error.context("logging in after reboot", logging.info)
        return self.wait_for_login(nic_index, timeout=timeout)


    def needs_restart(self, name, params, basedir):
        """
        Verifies whether the current virt_install commandline matches the
        requested one, based on the test parameters.
        """
        if (self.__make_libvirt_command() !=
                self.__make_libvirt_command(name, params, basedir)):
            logging.debug("VM params in env don't match requested, restarting.")
            return True
        else:
            logging.debug("VM params in env do match requested, continuing.")
            return False


    def screendump(self, filename, debug=False):
        if debug:
            logging.debug("Requesting screenshot %s" % filename)
        return virsh_screenshot(self.name, filename, self.connect_uri)


    def start(self):
        """
        Starts this VM.
        """
        self.uuid = virsh_uuid(self.name, self.connect_uri)
        # Pull in mac addresses from libvirt guest definition
        for index, nic in enumerate(self.virtnet):
            try:
                mac = self.get_virsh_mac_address(index)
                if not nic.has_key('mac'):
                    logging.debug("Updating nic %d with mac %s on vm %s"
                                  % (index, mac, self.name))
                    nic.mac = mac
                elif nic.mac.upper() != mac:
                    logging.warning("Requested mac %s doesn't match mac %s "
                                    "as defined for vm %s" % (nic.mac, mac,
                                    self.name))
                #TODO: Checkout/Set nic_model, nettype, netdst also
            except virt_vm.VMMACAddressMissingError:
                logging.warning("Nic %d requested by test but not defined for"
                                " vm %s" % (index, self.name))
        if virsh_start(self.name, self.connect_uri):
            # Wait for the domain to be created
            has_started = virt_utils.wait_for(func=self.is_alive, timeout=60,
                                              text=("waiting for domain %s "
                                                    "to start" % self.name))
            if has_started is None:
                raise virt_vm.VMStartError(self.name, "libvirt domain not "
                                                      "active after start")
            self.uuid = virsh_uuid(self.name, self.connect_uri)
        else:
            raise virt_vm.VMStartError(self.name, "libvirt domain failed "
                                                  "to start")


    def wait_for_shutdown(self, count=60):
        """
        Return True on successful domain shutdown.

        Wait for a domain to shutdown, libvirt does not block on domain
        shutdown so we need to watch for successful completion.

        @param name: VM name
        @param name: Optional timeout value
        """
        timeout = count
        while count > 0:
            # check every 5 seconds
            if count % 5 == 0:
                if virsh_is_dead(self.name, self.connect_uri):
                    logging.debug("Shutdown took %d seconds", timeout - count)
                    return True
            count -= 1
            time.sleep(1)
            logging.debug("Waiting for guest to shutdown %d", count)
        return False


    def shutdown(self):
        """
        Shuts down this VM.
        """
        if virsh_shutdown(self.name, self.connect_uri):
            if self.wait_for_shutdown():
                logging.debug("VM %s shut down", self.name)
                return True
            else:
                logging.error("VM %s failed to shut down", self.name)
                return False
        else:
            logging.error("VM %s failed to shut down", self.name)
            return False


    def pause(self):
        return virsh_suspend(self.name, self.connect_uri)


    def resume(self):
        return virsh_resume(self.name, self.connect_uri)


    def save_to_file(self, path):
        """
        Override BaseVM save_to_file method
        """
        virsh_save(self.name, path, uri=self.connect_uri)


    def restore_from_file(self, path):
        """
        Override BaseVM restore_from_file method
        """
        virsh_restore(self.name, path, uri=self.connect_uri)


    def vcpupin(self, vcpu, cpu):
        """
        To pin vcpu to cpu
        """
        virsh_vcpupin(self.name, vcpu, cpu)
