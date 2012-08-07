"""
Utility classes and functions to handle connection to a libvirt host system

@copyright: 2012 Red Hat Inc.
"""

import logging
from autotest.client.shared import error

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

