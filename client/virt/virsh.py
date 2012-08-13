"""
Utility classes and functions to handle connection to a libvirt host system

Suggested usage: from autotest.client.virt.virsh import Virsh

Virsh Function API:
    All module functions must accept a variable number of keyword arguments
    (i.e. **dargs) in addition to normal positional/keyword parameters.

@copyright: 2012 Red Hat Inc.
"""

import logging, urlparse
from autotest.client import utils, os_dep
from autotest.client.shared import error
from autotest.client.virt import aexpect, virt_vm

# Class-wide logging de-clutterer counter
_SCREENSHOT_ERROR_COUNT = 0

# Using properties here to allow extending getters/setters by external means
class VirshBase(object):
    """
    Base Class storing libvirt Connection & state to a host
    """

    # Private storage for properties set in __init__
    _uri = ""
    _ignore_status = False
    _debug = False
    _virsh_exec = os_dep.command("virsh")

    # Keep properties referencable and extensible by subclasses
    PROPERTIES = {
        'uri':('get_uri', 'set_uri'),
        'ignore_status':('get_ignore_status', 'set_ignore_status'),
        'virsh_exec':('get_virsh_exec', 'set_virsh_exec'),
        'debug':('get_debug', 'set_debug'),
    }

    def __init__(self, **dargs):
        """
        Initialize libvirt connection/state

        param: uri: default connection uri when not specified
        param: ignore_status: Treat command errors as real errors if False
        param: debug: Print additional output / debugging info.
        param: virsh_exec: optional/alternate virsh executable path
        """
        # setup properties from instance instead of class
        for name, handlers in self.PROPERTIES.items():
            getter = getattr(self, handlers[0])
            setter = getattr(self, handlers[1])
            setattr(self, name,  property(*(getter, setter)))
        # utilize properties for initialization
        for name, value in dargs:
            if value:
                setattr(self, name, value)


    def get_uri(self):
        return self._uri


    def set_uri(self, uri):
        self._uri = uri


    def get_ignore_status(self):
        return self._ignore_status


    def set_ignore_status(self, ignore_status):
        if ignore_status:
            self._ignore_status = True
        else:
            self._ignore_status = False


    def get_virsh_exec(self):
        return self._virsh_exec


    def set_virsh_exec(self, virsh_exec):
        self._virsh_exec = virsh_exec


    def get_debug(self):
        return self._debug


    def set_debug(self, debug):
        if debug:
            self._debug = True
            logging.debug("Virsh debugging switched on")
        else:
            self._debug = False
            logging.debug("Virsh debugging switched off")

# Ahhhhh, look out!  It's D Arg mangler comnta gettcha!
class DArgMangler(dict):
    """
    Dict-like class that checks parent instance properties for any missing keys
    """

    def __init__(self, parent, *args, **dargs):
        """
        Initialize DargMangler dict to fill missing keys from parent

        param: parent: Parent instance to pull properties from as needed
        """
        self._parent = parent
        super(DArgMangler, self).__init__(*args, **dargs)


    def __getitem__(self, key):
        try:
            value = super(DArgMangler, self).__getitem__(key)
            if value:
                return value
        except KeyError:
            value = getattr(self._parent, key)
            if value:
                return value
            else:
                raise KeyError, ":%s (parent %s)" % (str(key),
                                                     str(type(self._parent)))


class VirshSession(aexpect.ShellSession):
    """
    A virsh shell session, used with Virsh instances.
    """

    ERROR_REGEX_LIST = ['error:\s*', 'failed']

    def __init__(self, virsh_instance):
        uri_arg = ""
        if virsh_instance.uri:
            uri_arg = " -c '%s'" % virsh_instance.uri
        cmd = "%s%s" % (virsh_instance.virsh_exec, uri_arg)
        super(VirshSession, self).__init__(command=cmd,
                                            id=virsh_instance.session_id,
                                            prompt=r"virsh\s*\#\s*")


    # No way to get sub-command status so fake it with regex over output
    def cmd_status_output(self, cmd, timeout=60, internal_timeout=None,
                          print_func=None):
        o = self.cmd_output(cmd, timeout, internal_timeout, print_func)
        for line in o.splitlines():
            if self.match_patterns(line, self.ERROR_REGEX_LIST):
                # There was an error
                return 1, o
        return 0, o


class Virsh(VirshBase):
    """
    Execute libvirt operations, optionally with particular connection/state.
    """

    # list of module symbol names not to wrap inside instances
    _NOCLOSE = ['__builtins__', '__file__', '__package__', '__name__',
                '__doc__', 'DArgMangler', 'VirshBase', 'Virsh', '_SCREENSHOT_ERROR_COUNT',
                'VirshSession', '_cmd', 'cmd']

    session = None
    session_id = None

    def __init__(self, *args, **dargs):
        # new_session() called by super's __init__ via uri property
        super(Virsh, self).__init__(*args, **dargs)
        # Define the instance callables from the contents of this module
        # to avoid using class methods and hand-written aliases
        for sym, ref in globals().items():
            if sym not in self._NOCLOSE:
                # closure allowing virsh.function() API extension
                def virsh_closure(self, *args, **dargs):
                    # Allow extension of self.PROPERTIES by mangling
                    # closure keyword arguments through property managers
                    new_dargs = DArgMangler(self, dargs)
                    for prop in self.PROPERTIES.keys():
                        if not new_dargs.has_key(prop) or not new_dargs[prop]:
                            new_dargs[prop] = getattr(self, prop)
                    return ref(*args, **new_dargs)
                setattr(self, sym, virsh_closure)


    def new_session(self):
        if getattr(self, 'session_id') and getattr(self, 'session'):
            self.session.close()
        self.session = VirshSession(self)
        self.session_id = self.session.get_id()


    def set_uri(self, uri):
        """
        Change instances uri, and re-connect virsh shell session.
        """
        # Don't assume set_uri() wasn't overridden
        if super(Virsh, self).uri != uri:
            super(Virsh, self).uri = uri
            self.new_session()


    # Note: MANY other functions depend on cmd()'s parameter order and names
    def cmd(self, cmd, **dargs):
        uri = dargs.get('uri', self.uri)
        if dargs.get('uri'):
            _cmd(cmd, **dargs)
        # VirshSession Can't make these
        ret = utils.CmdResult(cmd)
        if dargs['debug']:
            logging.debug("Running command: %s" % cmd)
        ret.exit_status, ret.stdout = self.session.cmd_status_output(cmd)
        ret.stderr = "" # No way to retrieve this separetly
        if not dargs['ignore_status'] and bool(ret.exit_status):
            raise error.CmdError(cmd, ret,
                                 "Command returned non-zero exit status")
        if dargs['debug']:
            logging.debug("status: %s" % ret.exit_status)
            logging.debug("stdout: %s" % ret.stdout.strip())
            logging.debug("stderr: %s" % ret.stderr.strip())
        return ret


##### virsh functions follow #####


# Note: MANY other functions depend on cmd()'s parameter order and names
def _cmd(cmd, **dargs):
    """
    Interface to cmd function as 'cmd' symbol is polluted
    """

    uri_arg = " "
    if dargs['uri']:
        uri_arg = " -c '%s'" % dargs['uri']
    cmd = "%s%s%s" % (dargs['virsh_exec'], uri_arg, cmd)

    if dargs['debug']:
        logging.debug("Running command: %s" % cmd)

    ret = utils.run(cmd, verbose=dargs['debug'],
                    ignore_status=dargs['ignore_status'])

    if dargs['debug']:
        logging.debug("status: %s" % ret.exit_status)
        logging.debug("stdout: %s" % ret.stdout.strip())
        logging.debug("stderr: %s" % ret.stderr.strip())
    return ret


def cmd(cmd, **dargs):
    """
    Append cmd to 'virsh' and execute, optionally return full results.

    @param: cmd: Command line to append to virsh command
    @param: dargs: standardized virh function API keywords
    @return: CmdResult object
    """
    return _cmd(cmd, **dargs)


def domname(id, **dargs):
    """
    Convert a domain id or UUID to domain name

    @param id: a domain id or UUID.
    @param: dargs: standardized virh function API keywords
    @return: CmdResult object
    """
    return cmd("domname --domain %s" % id, **dargs)


def qemu_monitor_command(domname, command, **dargs):
    """
    This helps to execute the qemu monitor command through virsh command.

    @param: domname: Name of monitor domain
    @param: command: monitor command to execute
    @param: dargs: standardized virh function API keywords
    """

    cmd_qemu_monitor = "qemu-monitor-command %s --hmp \'%s\'" % (domname, command)
    return cmd(cmd_qemu_monitor, **dargs)


def vcpupin(domname, vcpu, cpu, **dargs):
    """
    Changes the cpu affinity for respective vcpu.

    @param: domname: name of domain
    @param: vcpu: virtual CPU to modify
    @param: cpu: physical CPU specification (string)
    @param: dargs: standardized virh function API keywords
    @return: True operation was successful
    """

    try:
        cmd_vcpupin = "vcpupin %s %s %s" % (domname, vcpu, cpu)
        cmd(cmd_vcpupin, **dargs)

    except error.CmdError, detail:
        logging.error("Virsh vcpupin VM %s failed:\n%s", domname, detail)
        return False


def vcpuinfo(domname, **dargs):
    """
    Prints the vcpuinfo of a given domain.

    @param: domname: name of domain
    @param: dargs: standardized virh function API keywords
    @return: standard output from command
    """

    cmd_vcpuinfo = "vcpuinfo %s" % domname
    return cmd(cmd_vcpuinfo, **dargs).stdout.strip()


def vcpucount_live(domname, **dargs):
    """
    Prints the vcpucount of a given domain.

    @param: domname: name of a domain
    @param: dargs: standardized virh function API keywords
    @return: standard output from command
    """

    cmd_vcpucount = "vcpucount --live --active %s" % domname
    return cmd(cmd_vcpucount, **dargs).stdout.strip()


def freecell(uri = "", extra="", **dargs):
    """
    Prints the available amount of memory on the machine or within a NUMA cell.

    @param: extra: extra argument string to pass to command
    @param: dargs: standardized virh function API keywords
    @return: CmdResult object
    """
    cmd_freecell = "freecell %s" % extra
    return cmd(cmd_freecell, **dargs)


def nodeinfo(uri = "", extra="", **dargs):
    """
    Returns basic information about the node,like number and type of CPU,
    and size of the physical memory.

    @param: extra: extra argument string to pass to command
    @param: dargs: standardized virh function API keywords
    @return: CmdResult object
    """
    cmd_nodeinfo = "nodeinfo %s" % extra
    return cmd(cmd_nodeinfo, **dargs)


def uri(**dargs):
    """
    Return the hypervisor canonical URI.

    @param: dargs: standardized virh function API keywords
    @return: standard output from command
    """
    return cmd("uri", **dargs).stdout.strip()


def hostname(**dargs):
    """
    Return the hypervisor hostname.

    @param: dargs: standardized virh function API keywords
    @return: standard output from command
    """
    return cmd("hostname", **dargs).stdout.strip()


def version(**dargs):
    """
    Return the major version info about what this built from.

    @param: dargs: standardized virh function API keywords
    @return: standard output from command
    """
    return cmd("version", **dargs).stdout.strip()


def driver(**dargs):
    """
    Return the driver by asking libvirt

    @param: dargs: standardized virh function API keywords
    @return: VM driver name
    """
    # libvirt schme composed of driver + command
    # ref: http://libvirt.org/uri.html
    scheme = urlparse.urlsplit( uri(**dargs) )[0]
    # extract just the driver, whether or not there is a '+'
    return scheme.split('+', 2)[0]


def domstate(name, **dargs):
    """
    Return the state about a running domain.

    @param name: VM name
    @param: dargs: standardized virh function API keywords
    @return: standard output from command
    """
    return cmd("domstate %s" % name, **dargs).stdout.strip()


def domid(name, **dargs):
    """
    Return VM's ID.

    @param name: VM name
    @param: dargs: standardized virh function API keywords
    @return: standard output from command
    """
    return cmd("domid %s" % (name), **dargs).stdout.strip()


def dominfo(name, **dargs):
    """
    Return the VM information.

    @param: dargs: standardized virh function API keywords
    @return: standard output from command
    """
    return cmd("dominfo %s" % (name), **dargs).stdout.strip()


def domuuid(name, **dargs):
    """
    Return the Converted domain name or id to the domain UUID.

    @param name: VM name
    @param: dargs: standardized virh function API keywords
    @return: standard output from command
    """
    return cmd("domuuid %s" % name, **dargs).stdout.strip()


def screenshot(name, filename, **dargs):
    """
    Capture a screenshot of VM's console and store it in file on host

    @param: name: VM name
    @param: filename: name of host file
    @param: dargs: standardized virh function API keywords
    @return: filename
    """
    try:
        cmd("screenshot %s %s" % (name, filename), **dargs)
    except error.CmdError, detail:
        if _SCREENSHOT_ERROR_COUNT < 1:
            logging.error("Error taking VM %s screenshot. You might have to "
                          "set take_regular_screendumps=no on your "
                          "tests.cfg config file \n%s.  This will be the "
                          "only logged error message.", name, detail)
        _SCREENSHOT_ERROR_COUNT += 1
    return filename


def dumpxml(name, to_file="", **dargs):
    """
    Return the domain information as an XML dump.

    @param: name: VM name
    @param: to_file: optional file to write XML output to
    @param: dargs: standardized virh function API keywords
    @return: standard output from command
    """
    if to_file:
        cmd = "dumpxml %s > %s" % (name, to_file)
    else:
        cmd = "dumpxml %s" % name

    return cmd(cmd, **dargs).stdout.strip()


def is_alive(name, **dargs):
    """
    Return True if the domain is started/alive.

    @param: name: VM name
    @param: dargs: standardized virh function API keywords
    @return: True operation was successful
    """
    return not is_dead(name, **dargs)


def is_dead(name, **dargs):
    """
    Return True if the domain is undefined or not started/dead.

    @param: name: VM name
    @param: dargs: standardized virh function API keywords
    @return: True operation was successful
    """
    try:
        state = domstate(name, **dargs)
    except error.CmdError:
        return True
    if state in ('running', 'idle', 'no state', 'paused'):
        return False
    else:
        return True


def suspend(name, **dargs):
    """
    True on successful suspend of VM - kept in memory and not scheduled.

    @param: name: VM name
    @param: dargs: standardized virh function API keywords
    @return: True operation was successful
    """
    try:
        cmd("suspend %s" % (name), **dargs)
        if domstate(name, **dargs) == 'paused':
            logging.debug("Suspended VM %s", name)
            return True
        else:
            return False
    except error.CmdError, detail:
        logging.error("Suspending VM %s failed:\n%s", name, detail)
        return False


def resume(name, **dargs):
    """
    True on successful moving domain out of suspend

    @param: name: VM name
    @param: dargs: standardized virh function API keywords
    @return: True operation was successful
    """
    try:
        cmd("resume %s" % (name), **dargs)
        if is_alive(name, **dargs):
            logging.debug("Resumed VM %s", name)
            return True
        else:
            return False
    except error.CmdError, detail:
        logging.error("Resume VM %s failed:\n%s", name, detail)
        return False


def save(name, path, **dargs):
    """
    Store state of VM into named file.

    @param: name: VM Name to operate on
    @param: path: absolute path to state file
    @param: dargs: standardized virh function API keywords
    """
    state = domstate(name, **dargs)
    if state not in ('paused',):
        raise virt_vm.VMStatusError("Cannot save a VM that is %s" % state)
    logging.debug("Saving VM %s to %s" %(name, path))
    cmd("save %s %s" % (name, path), **dargs)
    # libvirt always stops VM after saving
    state = domstate(name, **dargs)
    if state not in ('shut off',):
        raise virt_vm.VMStatusError("VM not shut off after save")


def restore(name, path, **dargs):
    """
    Load state of VM from named file and remove file.

    @param: name: VM Name to operate on
    @param: path: absolute path to state file.
    @param: dargs: standardized virh function API keywords
    """
    # Blindly assume named VM cooresponds with state in path
    # rely on higher-layers to take exception if missmatch
    state = domstate(name, **dargs)
    if state not in ('shut off',):
        raise virt_vm.VMStatusError("Can not restore VM that is %s" % state)
    logging.debug("Restoring VM from %s" % path)
    cmd("restore %s" % path, **dargs)
    state = domstate(name, **dargs)
    if state not in ('paused','running'):
        raise virt_vm.VMStatusError("VM not paused after restore, it is %s." %
                state)


def start(name, **dargs):
    """
    True on successful start of (previously defined) inactive domain.

    @param: name: VM name
    @param: dargs: standardized virh function API keywords
    @return: True operation was successful
    """
    if is_alive(name, **dargs):
        return True
    try:
        cmd("start %s" % (name), **dargs)
        return True
    except error.CmdError, detail:
        logging.error("Start VM %s failed:\n%s", name, detail)
        return False


def shutdown(name, **dargs):
    """
    True on successful domain shutdown.

    @param: name: VM name
    @param: dargs: standardized virh function API keywords
    @return: True operation was successful
    """
    if domstate(name, **dargs) == 'shut off':
        return True
    try:
        cmd("shutdown %s" % (name), **dargs)
        return True
    except error.CmdError, detail:
        logging.error("Shutdown VM %s failed:\n%s", name, detail)
        return False


def destroy(name, **dargs):
    """
    True on successful domain destruction

    @param: name: VM name
    @param: dargs: standardized virh function API keywords
    @return: True operation was successful
    """
    if domstate(name, **dargs) == 'shut off':
        return True
    try:
        cmd("destroy %s" % (name), **dargs)
        return True
    except error.CmdError, detail:
        logging.error("Destroy VM %s failed:\n%s", name, detail)
        return False


def define(xml_path, **dargs):
    """
    Return True on successful domain define.

    @param: xml_path: XML file path
    @param: dargs: standardized virh function API keywords
    @return: True operation was successful
    """
    try:
        cmd("define --file %s" % xml_path, **dargs)
        return True
    except error.CmdError:
        logging.error("Define %s failed.", xml_path)
        return False


def undefine(name, **dargs):
    """
    Return True on successful domain undefine (after sutdown/destroy).

    @param: name: VM name
    @param: dargs: standardized virh function API keywords
    @return: True operation was successful
    """
    try:
        cmd("undefine %s" % (name), **dargs)
        logging.debug("undefined VM %s", name)
        return True
    except error.CmdError, detail:
        logging.error("undefine VM %s failed:\n%s", name, detail)
        return False


def remove_domain(name, **dargs):
    """
    Return True after forcefully removing a domain if it exists.

    @param: name: VM name
    @param: dargs: standardized virh function API keywords
    @return: True operation was successful
    """
    if domain_exists(name, **dargs):
        if is_alive(name, **dargs):
            destroy(name, **dargs)
        undefine(name, **dargs)
    return True


def domain_exists(name, **dargs):
    """
    Return True if a domain exits.

    @param name: VM name
    @param: dargs: standardized virh function API keywords
    @return: True operation was successful
    """
    try:
        cmd("domstate %s" % name, **dargs)
        return True
    except error.CmdError, detail:
        logging.warning("VM %s does not exist:\n%s", name, detail)
        return False


def migrate(name="", dest_uri="", option="", extra="", **dargs):
    """
    Migrate a guest to another host.

    @param: name: name of guest on uri.
    @param: dest_uri: libvirt uri to send guest to
    @param: option: Free-form string of options to virsh migrate
    @param: extra: Free-form string of options to follow <domain> <desturi>
    @param: dargs: standardized virh function API keywords
    @return: CmdResult object
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

    return cmd(cmd, **dargs)


def attach_device(name, xml_file, extra="", **dargs):
    """
    Attach a device to VM.

    @param: name: name of guest
    @param: xml_file: xml describing device to detach
    @param: extra: additional arguments to command
    @param: dargs: standardized virh function API keywords
    @return: True operation was successful
    """
    cmd = "attach-device --domain %s --file %s %s" % (name, xml_file, extra)
    try:
        cmd(cmd, **dargs)
        return True
    except error.CmdError:
        logging.error("Attaching device to VM %s failed." % name)
        return False


def detach_device(name, xml_file, extra="", **dargs):
    """
    Detach a device from VM.

    @param: name: name of guest
    @param: xml_file: xml describing device to detach
    @param: extra: additional arguments to command
    @param: dargs: standardized virh function API keywords
    @return: True operation was successful
    """
    cmd = "detach-device --domain %s --file %s %s" % (name, xml_file, extra)
    try:
        cmd(cmd, **dargs)
        return True
    except error.CmdError:
        logging.error("Detaching device from VM %s failed." % name)
        return False


def attach_interface(name, option="", **dargs):
    """
    Attach a NIC to VM.

    @param: name: name of guest
    @param: option: options to pass to command
    @param: dargs: standardized virh function API keywords
    @return: CmdResult object
    """
    cmd = "attach-interface "

    if name:
        cmd += "--domain %s" % name
    if option:
        cmd += " %s" % option

    return cmd(cmd, **dargs)


def detach_interface(name, option="", **dargs):
    """
    Detach a NIC to VM.

    @param: name: name of guest
    @param: option: options to pass to command
    @param: dargs: standardized virh function API keywords
    @return: CmdResult object
    """
    cmd = "detach-interface "

    if name:
        cmd += "--domain %s" % name
    if option:
        cmd += " %s" % option

    return cmd(cmd, **dargs)


def net_create(xml_file, extra="", **dargs):
    """
    Create network from a XML file.

    @param: xml_file: xml defining network
    @param: extra: extra parameters to pass to command
    @param: options: options to pass to command
    @param: dargs: standardized virh function API keywords
    @return: CmdResult object
    """
    cmd = "net-create --file %s %s" % (xml_file, extra)
    return cmd(cmd, **dargs)


def net_list(options, extra="", **dargs):
    """
    List networks on host.

    @param: extra: extra parameters to pass to command
    @param: options: options to pass to command
    @param: dargs: standardized virh function API keywords
    @return: CmdResult object
    """
    cmd = "net-list %s %s" % (options, extra)
    return cmd(cmd, **dargs)


def net_destroy(name, extra="", **dargs):
    """
    Destroy actived network on host.

    @param: name: name of guest
    @param: extra: extra string to pass to command
    @param: dargs: standardized virh function API keywords
    @return: CmdResult object
    """
    cmd = "net-destroy --network %s %s" % (name, extra)
    return cmd(cmd, **dargs)

