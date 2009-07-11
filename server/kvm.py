#
# Copyright 2007 Google Inc. Released under the GPL v2

"""
This module defines the KVM class

        KVM: a KVM virtual machine monitor
"""

__author__ = """
mbligh@google.com (Martin J. Bligh),
poirier@google.com (Benjamin Poirier),
stutsman@google.com (Ryan Stutsman)
"""

import os

from autotest_lib.client.common_lib import error
from autotest_lib.server import hypervisor, utils, hosts


_qemu_ifup_script= """\
#!/bin/sh
# $1 is the name of the new qemu tap interface

ifconfig $1 0.0.0.0 promisc up
brctl addif br0 $1
"""

_check_process_script= """\
if [ -f "%(pid_file_name)s" ]
then
        pid=$(cat "%(pid_file_name)s")
        if [ -L /proc/$pid/exe ] && stat /proc/$pid/exe |
                grep -q --  "-> \`%(qemu_binary)s\'\$"
        then
                echo "process present"
        else
                rm -f "%(pid_file_name)s"
                rm -f "%(monitor_file_name)s"
        fi
fi
"""

_hard_reset_script= """\
import socket

monitor_socket= socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
monitor_socket.connect("%(monitor_file_name)s")
monitor_socket.send("system_reset\\n")\n')
"""

_remove_modules_script= """\
if $(grep -q "^kvm_intel [[:digit:]]\+ 0" /proc/modules)
then
        rmmod kvm-intel
fi

if $(grep -q "^kvm_amd [[:digit:]]\+ 0" /proc/modules)
then
        rmmod kvm-amd
fi

if $(grep -q "^kvm [[:digit:]]\+ 0" /proc/modules)
then
        rmmod kvm
fi
"""


class KVM(hypervisor.Hypervisor):
    """
    This class represents a KVM virtual machine monitor.

    Implementation details:
    This is a leaf class in an abstract class hierarchy, it must
    implement the unimplemented methods in parent classes.
    """

    build_dir= None
    pid_dir= None
    support_dir= None
    addresses= []
    insert_modules= True
    modules= {}


    def __del__(self):
        """
        Destroy a KVM object.

        Guests managed by this hypervisor that are still running will
        be killed.
        """
        self.deinitialize()


    def _insert_modules(self):
        """
        Insert the kvm modules into the kernel.

        The modules inserted are the ones from the build directory, NOT
        the ones from the kernel.

        This function should only be called after install(). It will
        check that the modules are not already loaded before attempting
        to insert them.
        """
        cpu_flags= self.host.run('cat /proc/cpuinfo | '
                'grep -e "^flags" | head -1 | cut -d " " -f 2-'
                ).stdout.strip()

        if cpu_flags.find('vmx') != -1:
            module_type= "intel"
        elif cpu_flags.find('svm') != -1:
            module_type= "amd"
        else:
            raise error.AutoservVirtError("No harware "
                    "virtualization extensions found, "
                    "KVM cannot run")

        self.host.run('if ! $(grep -q "^kvm " /proc/modules); '
                'then insmod "%s"; fi' % (utils.sh_escape(
                os.path.join(self.build_dir, "kernel/kvm.ko")),))
        if module_type == "intel":
            self.host.run('if ! $(grep -q "^kvm_intel " '
                    '/proc/modules); then insmod "%s"; fi' %
                    (utils.sh_escape(os.path.join(self.build_dir,
                    "kernel/kvm-intel.ko")),))
        elif module_type == "amd":
            self.host.run('if ! $(grep -q "^kvm_amd " '
                    '/proc/modules); then insmod "%s"; fi' %
                    (utils.sh_escape(os.path.join(self.build_dir,
                    "kernel/kvm-amd.ko")),))


    def _remove_modules(self):
        """
        Remove the kvm modules from the kernel.

        This function checks that they're not in use before trying to
        remove them.
        """
        self.host.run(_remove_modules_script)


    def install(self, addresses, build=True, insert_modules=True, syncdir=None):
        """
        Compile the kvm software on the host that the object was
        initialized with.

        The kvm kernel modules are compiled, for this, the kernel
        sources must be available. A custom qemu is also compiled.
        Note that 'make install' is not run, the kernel modules and
        qemu are run from where they were built, therefore not
        conflicting with what might already be installed.

        Args:
                addresses: a list of dict entries of the form
                        {"mac" : "xx:xx:xx:xx:xx:xx",
                        "ip" : "yyy.yyy.yyy.yyy"} where x and y
                        are replaced with sensible values. The ip
                        address may be a hostname or an IPv6 instead.

                        When a new virtual machine is created, the
                        first available entry in that list will be
                        used. The network card in the virtual machine
                        will be assigned the specified mac address and
                        autoserv will use the specified ip address to
                        connect to the virtual host via ssh. The virtual
                        machine os must therefore be configured to
                        configure its network with the ip corresponding
                        to the mac.
                build: build kvm from the source material, if False,
                        it is assumed that the package contains the
                        source tree after a 'make'.
                insert_modules: build kvm modules from the source
                        material and insert them. Otherwise, the
                        running kernel is assumed to already have
                        kvm support and nothing will be done concerning
                        the modules.

        TODO(poirier): check dependencies before building
        kvm needs:
        libasound2-dev
        libsdl1.2-dev (or configure qemu with --disable-gfx-check, how?)
        bridge-utils
        """
        self.addresses= [
                {"mac" : address["mac"],
                "ip" : address["ip"],
                "is_used" : False} for address in addresses]

        self.build_dir = self.host.get_tmp_dir()
        self.support_dir= self.host.get_tmp_dir()

        self.host.run('echo "%s" > "%s"' % (
                utils.sh_escape(_qemu_ifup_script),
                utils.sh_escape(os.path.join(self.support_dir,
                        "qemu-ifup.sh")),))
        self.host.run('chmod a+x "%s"' % (
                utils.sh_escape(os.path.join(self.support_dir,
                        "qemu-ifup.sh")),))

        self.host.send_file(self.source_material, self.build_dir)
        remote_source_material= os.path.join(self.build_dir,
                        os.path.basename(self.source_material))

        self.build_dir= utils.unarchive(self.host,
                remote_source_material)

        if insert_modules:
            configure_modules= ""
            self.insert_modules= True
        else:
            configure_modules= "--with-patched-kernel "
            self.insert_modules= False

        # build
        if build:
            try:
                self.host.run('make -C "%s" clean' % (
                        utils.sh_escape(self.build_dir),),
                        timeout=600)
            except error.AutoservRunError:
                # directory was already clean and contained
                # no makefile
                pass
            self.host.run('cd "%s" && ./configure %s' % (
                    utils.sh_escape(self.build_dir),
                    configure_modules,), timeout=600)
            if syncdir:
                cmd = 'cd "%s/kernel" && make sync LINUX=%s' % (
                utils.sh_escape(self.build_dir),
                utils.sh_escape(syncdir))
                self.host.run(cmd)
            self.host.run('make -j%d -C "%s"' % (
                    self.host.get_num_cpu() * 2,
                    utils.sh_escape(self.build_dir),), timeout=3600)
            # remember path to modules
            self.modules['kvm'] = "%s" %(
                    utils.sh_escape(os.path.join(self.build_dir,
                    "kernel/kvm.ko")))
            self.modules['kvm-intel'] = "%s" %(
                    utils.sh_escape(os.path.join(self.build_dir,
                    "kernel/kvm-intel.ko")))
            self.modules['kvm-amd'] = "%s" %(
                    utils.sh_escape(os.path.join(self.build_dir,
                    "kernel/kvm-amd.ko")))
            print self.modules

        self.initialize()


    def initialize(self):
        """
        Initialize the hypervisor.

        Loads needed kernel modules and creates temporary directories.
        The logic is that you could compile once and
        initialize - deinitialize many times. But why you would do that
        has yet to be figured.

        Raises:
                AutoservVirtError: cpuid doesn't report virtualization
                        extentions (vmx for intel or svm for amd), in
                        this case, kvm cannot run.
        """
        self.pid_dir= self.host.get_tmp_dir()

        if self.insert_modules:
            self._remove_modules()
            self._insert_modules()


    def deinitialize(self):
        """
        Terminate the hypervisor.

        Kill all the virtual machines that are still running and
        unload the kernel modules.
        """
        self.refresh_guests()
        for address in self.addresses:
            if address["is_used"]:
                self.delete_guest(address["ip"])
        self.pid_dir= None

        if self.insert_modules:
            self._remove_modules()


    def new_guest(self, qemu_options):
        """
        Start a new guest ("virtual machine").

        Returns:
                The ip that was picked from the list supplied to
                install() and assigned to this guest.

        Raises:
                AutoservVirtError: no more addresses are available.
        """
        for address in self.addresses:
            if not address["is_used"]:
                break
        else:
            raise error.AutoservVirtError(
                    "No more addresses available")

        retval= self.host.run(
                '%s'
                # this is the line of options that can be modified
                ' %s '
                '-pidfile "%s" -daemonize -nographic '
                #~ '-serial telnet::4444,server '
                '-monitor unix:"%s",server,nowait '
                '-net nic,macaddr="%s" -net tap,script="%s" -L "%s"' % (
                utils.sh_escape(os.path.join(
                        self.build_dir,
                        "qemu/x86_64-softmmu/qemu-system-x86_64")),
                qemu_options,
                utils.sh_escape(os.path.join(
                        self.pid_dir,
                        "vhost%s_pid" % (address["ip"],))),
                utils.sh_escape(os.path.join(
                        self.pid_dir,
                        "vhost%s_monitor" % (address["ip"],))),
                utils.sh_escape(address["mac"]),
                utils.sh_escape(os.path.join(
                        self.support_dir,
                        "qemu-ifup.sh")),
                utils.sh_escape(os.path.join(
                        self.build_dir,
                        "qemu/pc-bios")),))

        address["is_used"]= True
        return address["ip"]


    def refresh_guests(self):
        """
        Refresh the list of guests addresses.

        The is_used status will be updated according to the presence
        of the process specified in the pid file that was written when
        the virtual machine was started.

        TODO(poirier): there are a lot of race conditions in this code
        because the process might terminate on its own anywhere in
        between
        """
        for address in self.addresses:
            if address["is_used"]:
                pid_file_name= utils.sh_escape(os.path.join(
                        self.pid_dir,
                        "vhost%s_pid" % (address["ip"],)))
                monitor_file_name= utils.sh_escape(os.path.join(
                        self.pid_dir,
                        "vhost%s_monitor" % (address["ip"],)))
                retval= self.host.run(
                        _check_process_script % {
                        "pid_file_name" : pid_file_name,
                        "monitor_file_name" : monitor_file_name,
                        "qemu_binary" : utils.sh_escape(
                                os.path.join(self.build_dir,
                                "qemu/x86_64-softmmu/"
                                "qemu-system-x86_64")),})
                if (retval.stdout.strip() !=
                        "process present"):
                    address["is_used"]= False


    def delete_guest(self, guest_hostname):
        """
        Terminate a virtual machine.

        Args:
                guest_hostname: the ip (as it was specified in the
                        address list given to install()) of the guest
                        to terminate.

        Raises:
                AutoservVirtError: the guest_hostname argument is
                        invalid

        TODO(poirier): is there a difference in qemu between
        sending SIGTEM or quitting from the monitor?
        TODO(poirier): there are a lot of race conditions in this code
        because the process might terminate on its own anywhere in
        between
        """
        for address in self.addresses:
            if address["ip"] == guest_hostname:
                if address["is_used"]:
                    break
                else:
                    # Will happen if deinitialize() is
                    # called while guest objects still
                    # exit and these are del'ed after.
                    # In that situation, nothing is to
                    # be done here, don't throw an error
                    # either because it will print an
                    # ugly message during garbage
                    # collection. The solution would be to
                    # delete the guest objects before
                    # calling deinitialize(), this can't be
                    # done by the KVM class, it has no
                    # reference to those objects and it
                    # cannot have any either. The Guest
                    # objects already need to have a
                    # reference to their managing
                    # hypervisor. If the hypervisor had a
                    # reference to the Guest objects it
                    # manages, it would create a circular
                    # reference and those objects would
                    # not be elligible for garbage
                    # collection. In turn, this means that
                    # the KVM object would not be
                    # automatically del'ed at the end of
                    # the program and guests that are still
                    # running would be left unattended.
                    # Note that this circular reference
                    # problem could be avoided by using
                    # weakref's in class KVM but the
                    # control file will most likely also
                    # have references to the guests.
                    return
        else:
            raise error.AutoservVirtError("Unknown guest hostname")

        pid_file_name= utils.sh_escape(os.path.join(self.pid_dir,
                "vhost%s_pid" % (address["ip"],)))
        monitor_file_name= utils.sh_escape(os.path.join(self.pid_dir,
                "vhost%s_monitor" % (address["ip"],)))

        retval= self.host.run(
                _check_process_script % {
                "pid_file_name" : pid_file_name,
                "monitor_file_name" : monitor_file_name,
                "qemu_binary" : utils.sh_escape(os.path.join(
                        self.build_dir,
                        "qemu/x86_64-softmmu/qemu-system-x86_64")),})
        if retval.stdout.strip() == "process present":
            self.host.run('kill $(cat "%s")' %(
                    pid_file_name,))
            self.host.run('rm -f "%s"' %(
                    pid_file_name,))
            self.host.run('rm -f "%s"' %(
                    monitor_file_name,))
        address["is_used"]= False


    def reset_guest(self, guest_hostname):
        """
        Perform a hard reset on a virtual machine.

        Args:
                guest_hostname: the ip (as it was specified in the
                        address list given to install()) of the guest
                        to terminate.

        Raises:
                AutoservVirtError: the guest_hostname argument is
                        invalid
        """
        for address in self.addresses:
            if address["ip"] is guest_hostname:
                if address["is_used"]:
                    break
                else:
                    raise error.AutoservVirtError("guest "
                            "hostname not in use")
        else:
            raise error.AutoservVirtError("Unknown guest hostname")

        monitor_file_name= utils.sh_escape(os.path.join(self.pid_dir,
                "vhost%s_monitor" % (address["ip"],)))

        self.host.run('python -c "%s"' % (utils.sh_escape(
                _hard_reset_script % {
                "monitor_file_name" : monitor_file_name,}),))
