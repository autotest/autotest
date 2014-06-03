==========================
Autotest Remote (Autoserv)
==========================

Autoserv is a framework for "automating machine control"

Autoserv's purpose is to control machines, it can:

-  power cycle
-  install kernels
-  modify bootloader entries
-  run arbitrary commands
-  run Autotest Local (client) tests
-  transfer files

A machine can be:

-  local
-  remote (through ssh and conmux)
-  virtual (through kvm)

Control Files
-------------

In a way similar to Autotest, Autoserv uses control files. Those control
files use different commands than the Autotest ones but like the
Autotest ones they are processed by the python interpreter so they
contain functions provided by Autoserv and can contain python
statements.

Here is an example control file that installs a .deb packaged kernel on
a remote host controlled through ssh. If this file is placed in the
``server/`` directory and named "``example.control``", it can be
executed as ``./autoserv example.control`` from within the ``server/``
directory:

::

    remote_host= hosts.SSHHost("192.168.1.1")

    print remote_host.run("uname -a").stdout

    kernel= deb_kernel.DEBKernel()
    kernel.get("/var/local/linux-2.6.22.deb")

    print kernel.get_version()
    print kernel.get_image_name()
    print kernel.get_initrd_name()

    kernel.install(remote_host)

    remote_host.reboot()

    print remote_host.run("uname -a").stdout

Hosts
-----

"Host" objects are the work horses of Autoserv control files. There are
Host objects for machines controlled through ssh, through conmux or
virtual machines. The structure of the code was planned so that support
for other types of hosts can be added if necessary. If you add support
for another type of host, make sure to add that host to the
``server/hosts/__init__.py`` file.

Main Host Methods
~~~~~~~~~~~~~~~~~

Here are the most commonly used Host methods. Every type of host should
implement these and support at least the options listed. Specific hosts
may support more commands or more options. For information on these, see
the associated source file for the host type in the ``server/hosts/``
subdirectory of Autotest. This listing is not a substitute for the
source code function headers of those files, it's only a short summary.
In particular, have a look at the ``server/hosts/ssh_host.py`` file.

-  run(command)
-  reboot()
-  get\_file(source, dest)
-  send\_file(source, dest)
-  get\_tmp\_dir()
-  is\_up()
-  wait\_up(timeout)
-  wait\_down(timeout)
-  get\_num\_cpu()

CmdResult Objects
^^^^^^^^^^^^^^^^^^

The return value from a run() call is a CmdResult object. This object
contains information about the command and its execution. It is defined
and its documentation is in the file ``server/hosts/base_classes.py``.
CmdResult objects can be printed and they will output all their
information. Each field can also be accessed separately. The list of
fields is:

-  command: String containing the command line itself
-  exit\_status: Integer exit code of the process
-  stdout: String containing stdout of the process
-  stderr: String containing stderr of the process
-  duration: Elapsed wall clock time running the process
-  aborted: Signal that caused the command to terminate (0 if none)

Main types of Host
~~~~~~~~~~~~~~~~~~

SSHHost
^^^^^^^

SSHHost is probably the most common and most useful type of host. It
represents a remote machine controlled through an ssh session. It
supports all the `base methods for
hosts <Autoserv#mainHostMethods>`_ and features a run() function
that supports timeouts. SSHHost uses ssh to run commands and scp to
transfer files.

In order to use an SSHHost the remote machine must be configured for
password-less login, for example through public key authentication. An
SSHHost object is built by specifying a host name and, optionally, a
user name and port number.

ConmuxSSHHost
^^^^^^^^^^^^^

ConmuxSSHHost is an extension of SSHHost. It is for machines that use
Conmux (`HOWTO <Conmux/Howto>`_). These support hard reset through
the hardreset() method.

SiteHost
^^^^^^^^^

Site host is an empty class that is there to add site-specific methods
or attributes to all types of hosts. It is defined in the file
``server/hosts/site_host.py`` but this file may be left empty, as it is,
or removed altogether. Things that come to mind for this class are
functions for flashing a BIOS, determining hardware versions or other
operations that are too specific to be of general use. Naturally,
control files that use these functions cannot really be distributed but
at least they can use the generic host types like SSHHost without
directly modifying those.

KVMGuest
^^^^^^^^

KVMGuest represents a KVM virtual machine on which you can run programs.
It must be bound to another host, the machine that actually runs the
hypervisor. A KVMGuest is very similar to an SSHHost but it also
supports "hard reset" through the hardreset() method (implemented in
Guest) which commands the hypervisor to reset the guest. Please see the
`KVM section <Autoserv#kvmSupport>`_ for more information on KVM
and KVM guests.

LocalHost
^^^^^^^^^^

Early versions of Autoserv represented the local machine (the one
Autoserv runs on) as part of the Host hierarchy. This is no longer the
case however because it was felt that some of the Host operations did
not make sense on the local machine (wait\_down() for example).

Bootloader
~~~~~~~~~~

Boottool is a Perl script to query and modify boot loader entries.
Autoserv provides the Bootloader class, a wrapper around boottool.
Autoserv copies the boottool script automatically to a temporary
directory the first time it is needed. Please see the
``server/hosts/bootloader.py`` file for information on all supported
methods. The most important one is add\_kernel().

When adding a kernel, boottool's default behavior is to reuse the
command line of the first kernel entry already present in the bootloader
configuration and use it to deduce the options to specify for the new
entry.

InstallableObject
------------------

An InstallableObject represents a software package that can be
installed on a host. It is characterized by two methods:

-  get(location)
-  install(host)

get() is responsible for fetching the source material for the software
package. It can take many types of arguments as the location:

-  a local file or directory
-  a URL (http or ftp)
-  a python file-like object
-  if the argument doesn't look like any of the above, get() will assume
   that it is a string that represents the content itself

get() will store the content in a temporary folder on the host. This
way, it can be fetched once and installed on many hosts. install() will
install the software package on a host, typically in a temporary
directory.

Autotest Support
----------------

Autoserv includes specific support for Autotest. It can install Autotest
on a Host, run an Autotest control file and fetch the results back to
the server. This is done through the Autotest and Run classes in
``server/autotest.py``. The Autotest object is an InstallableObject. To
use it, you have to:

-  specify the source material via get()
   The Autotest object is special in this regard. If you do not specify
   any source, it will use the Autotest svn repository to fetch the
   software. This will be done on the target Host.
-  install() it on a host
   When installing itself, Autotest will look for a
   ``/etc/autotest.conf`` file on the target host with a format similar
   to the following:

   ::

       autodir=/usr/local/autotest/

-  run() a control file
   The run() syntax is the following: run(control\_file, results\_dir,
   host) The control\_file argument supports the same types of value as
   the get() method of InstallableObject (they use the same function
   behind the scenes)

Here is an example Autoserv control file to run an Autotest job, the
results will be transfered to the "job\_results" directory on the server
(the machine Autoserv is running on).

::

    remote_host= hosts.SSHHost("192.168.1.1")

    at= autotest.Autotest()
    at.get("/var/local/autotest/client")
    at.install(remote_host)

    control_file= """
    job.profilers.add("oprofile", events= ["CPU_CLK_UNHALTED:8000"])
    job.run_test("linus_stress")
    """

    results_dir= "job_results"

    at.run(control_file, results_dir, remote_host)

Kernel Objects
--------------

Kernel objects are another type of InstallableObjects. Support is
planned for kernels compiled from source and binary kernels packaged as
.rpm and .deb. At the moment (Autotest revision 626), only .deb kernels
are implemented. Some support for kernels from source is already in
Autotest. Kernels support the following methods:

-  get(location)
    customary InstallableObject method
-  install(host, extra arguments to boottool)
   When a kernel is installed on a host, it will use boottool to make
   itself the default kernel to boot. If you want to specify additional
   arguments, you can do so and they will be passed to the add\_kernel()
   method of the `boot loader <Autoserv#bootloader>`_.
-  get\_version()
-  get\_image\_name()
-  get\_initrd\_name()

As always, see the source file function headers for complete details,
for example see the file ``server/deb_kernel.py``

DEBKernels have an additional method, extract(host). This method will
extract the content the package to a temporary directory on the
specified Host. This is not a step of the install process, it is if you
want to access the content of the package without installing it. A
`possible usage <Autoserv#QEMUWay>`_ of that function is with kvm
and qemu's ``-kernel`` option.

Here is an example Autoserv control file to install a kernel:

::

    rh= hosts.SSHHost("192.168.1.1")

    print rh.run("uname -a").stdout

    kernel= deb_kernel.DEBKernel()
    kernel.get("/var/local/linux-2.6.22.deb")

    kernel.install(rh)

    rh.reboot()

    print rh.run("uname -a").stdout

A similar example using an RPM kernel and allowing the hosts to be
specified from the autoserv commandline
(``autoserv -m host1,host2 install-rpm``, for example):

::

    if not machines:
        raise "Specify the machines to run on via the -m flag"

    hosts = [hosts.SSHHost(h) for h in machines]

    kernel = rpm_kernel.RPMKernel()
    kernel.get('/stuff/kernels/kernel-smp-2.6.18.x86_64.rpm')

    for host in hosts:
        print host.run("uname -a").stdout
        kernel.install(host, default=True)
        host.reboot()
        print host.run("uname -a").stdout

    print "Done."

KVM Support
-----------

As stated previously, Autoserv supports controlling virtual machines.
The object model has been designed so that various types of "virtual
machine monitors"/hypervisors can be supported. At the moment (Autotest
revision 626), only `KVM <http://www.linux-kvm.org/page/Main_Page>`_ support is
included. In order to use KVM you must do the following:

#. create a Host, this will be machine that runs the hypervisor
#. create the KVM object, specify the source material for it via get(),
   and install it on that host
   The KVM InstallableObject is special in the sense that once it is
   installed on a Host, it is bound to that Host. This is because some
   status is maintained in the KVM object about the virtual machines
   that are running.
#. create KVMGuest objects, you have to specify, among other things, the
   KVM object created above
#. use the KVMGuest object like any other type of Host to run commands,
   change kernel, run Autotest, ...

Please see the files ``server/kvm.py`` and ``server/hosts/kvm_guest.py``
for more information on the parameters required, in particular, have a
look at the function headers of KVM.install() and the KVMGuest
constructor.

Here is an example Autoserv control file to do the above. Line 5
includes a list comprehension to create the required `address
list <Autoserv#IPAddressConfiguration>`_, remember that the control
files are python.

::

    remote_host= hosts.SSHHost("192.168.1.1")

    kvm_on_remote_host= kvm.KVM(remote_host)
    kvm_on_remote_host.get("/var/local/src/kvm-33.tar.gz")
    addresses= [{"mac": "02:00:00:00:00:%02x" % (num,), "ip" : "192.168.2.%d" % (num,)} for num in range(1, 32)]
    kvm_on_remote_host.install(addresses)

    qemu_options= "-m 256 -hda /var/local/vdisk.img -snapshot"
    g= hosts.KVMGuest(kvm_on_remote_host, qemu_options)
    g.wait_up()

    print g.run('uname -a').stdout.strip()

Compiling Options
~~~~~~~~~~~~~~~~~

You have to specify the source package for kvm, this should be an
archive from
`http://sourceforge.net/project/showfiles.phpgroup\_id=180599 <http://sourceforge.net/project/showfiles.phpgroup_id=180599>`_.
When the KVM object is installed you have the control over two options:
build (default True) and insert\_modules (default True).

If ``build`` is True, Autoserv will execute ``configure`` and ``make``
to build the KVM client and kernel modules from the source material.
``make install`` will never be performed, to avoid disturbing an already
present install of kvm on the system. In order for the build to succeed,
the kernel source has to be present (``/lib/modules/$(uname -r)/build``
points to the appropriate directory). If ``build`` is False,
``configure`` and ``make`` should have been executed already and the
binaries should be present in the source directory that was specified to
get() (in `step 2 <Autoserv#KVMSupportSteps>`_). You can also
re-archive (tar) the source directories after building kvm if you wish
and specify an archive to get().

If ``insert_modules`` is True, Autoserv will first remove the kvm
modules if they are present and insert the ones from the source material
(that might have just been compiled or might have been already compiled,
depending on the ``build`` option) when doing the install(). When the
KVM object is deleted, it will also remove the modules from the kernel.
At the moment, Autoserv will check for the appropriate type of kernel
modules to insert, kvm-amd or kvm-intel. It will not check if ``qemu``
or ``qemu-system-x86_64`` should be used however, it always uses the
latter. If ``insert_modules`` is False, the running kernel is assumed to
already have kvm support and nothing will be done concerning the
modules.

In short:

-  If your kernel already includes appropriate kvm support, run
   install(addresses, build=True, insert\_modules=False) or
   install(addresses, build=False, insert\_modules=False) depending on
   wether you have the source for the running kernel. If kvm kernel
   support is compiled as modules, make sure that they are loaded before
   instantiating a KVMGuest, possibly using a command like this
   ``remote_host.run("modprobe kvm-intel")`` in your control file.
-  If the kernel source will be present on the host, run
   install(addresses, build=True, insert\_modules=True)
-  Otherwise, compile the kvm sources on the server or another machine
   before running Autoserv and run install(addresses, build=False,
   insert\_modules=True)

Kernel Considerations
~~~~~~~~~~~~~~~~~~~~~

Here are some kernel configuration options that might be relevant when
you build your kernels.

Host Kernel
^^^^^^^^^^^

``CONFIG_HPET_EMULATE_RTC``, from the `kvm
faq <http://kvm.qumranet.com/kvmwiki/FAQ#head-ba9cf8ea65a0023b2cba804f14b013ff556f9b3f>`_:
I get "rtc interrupts lost" messages, and the guest is very slow

``KVM, KVM_AMD, KVM_INTEL``, if your kernel is recent enough and you
want to have kvm support from the kernel

Guest Kernel
^^^^^^^^^^^^

There are no specific needs for the guest kernel, so long as it can run
under qemu, it is OK. Qemu emulates an IDE hard disk. Many distribution
kernels use ide and ide\_generic drivers so sticking with those instead
of the newer libata potentially avoids device name changes from /dev/hda
to /dev/sda. These can be compiled as modules, in which case an initrd
will be needed. There is no real need for that however, compiling in the
IDE drivers avoids the need for an initrd, this will ease the use of the
qemu ``-kernel`` `option <Autoserv#QEMUWay>`_.

Disk Image Considerations
~~~~~~~~~~~~~~~~~~~~~~~~~

The disk image must be specified as a qemu option, as in the example
above:

::

    qemu_options= "-m 256 -hda /var/local/vdisk.img -snapshot"
    g= hosts.KVMGuest(kvm_on_remote_host, qemu_options)

Here ``/var/local/vdisk.img`` is the disk image and ``-snapshot``
instructs qemu not to modify the disk image, changes are discarded after
the virtual machine terminates. Please refer to the `QEMU
Documentation <http://wiki.qemu.org/Manual>`_ for
more information on the options you can pass to qemu.

IP Address Configuration
^^^^^^^^^^^^^^^^^^^^^^^^

A few things have to be considered for the guest disk image. The most
important one is specified in the kvm.py:intall() documentation: "The
virtual machine os must therefore be configured to configure its network
with the ip corresponding to the mac". Autoserv can only control the mac
address of the virtual machine through qemu but it will attempt to
contact it by its ip. You specify the mac-ip mapping in the install()
function but you also have to make sure that when the virtual machine
boots it acquires/uses the right ip. If you only want to spawn one
virtual machine at a time you can set the ip statically on the guest
disk image. If on the other hand you want to spawn many guests from the
same disk image, you can assign ip's from a properly configured dhcp
server or you can have the os of the virtual machine choose an ip based
on its mac. One way to do this with Debian compatible GNU/Linux
distributions is through the ``/etc/network/interfaces`` file with a
content similar to the following:

::

    auto eth0
    mapping eth0
            script /usr/local/bin/get-mac-address.sh
            map 02:00:00:00:00:01 vhost1
            map 02:00:00:00:00:02 vhost2

    iface vhost1 inet static
            address 10.0.2.1
            netmask 255.0.0.0
            gateway 10.0.0.1
    iface vhost2 inet static
            address 10.0.2.2
            netmask 255.0.0.0
            gateway 10.0.0.1

The file ``/usr/local/bin/get-mac-address.sh`` is the following:

::

    #!/bin/sh

    set -e

    export LANG=C

    iface="$1"
    mac=$(/sbin/ifconfig "$iface" | sed -n -e '/^.*HWaddr \([:[:xdigit:]]*\).*/{s//\1/;y/ABCDEF/abcdef/;p;q;}')
    which=""

    while read testmac scheme; do
            if [ "$which" ]; then continue; fi
            if [ "$mac" = "$(echo "$testmac" | sed -e 'y/ABCDEF/abcdef/')" ]; then which="$scheme"; fi
    done

    if [ "$which" ]; then echo $which; exit 0; fi
    exit 1

The ``/etc/network/interfaces`` file is repetitive and tedious to write,
instead it can be generated with the following python script. Make sure
to adjust the values for ``map_entry``, ``host_entry``, ``first_value``
and ``last_value``:

::

    #!/usr/bin/python

    header= """# This file describes the network interfaces available on your system
    # and how to activate them. For more information, see interfaces(5).

    # The loopback network interface
    auto lo
    iface lo inet loopback

    # The primary network interface
    auto eth0
    mapping eth0
            script /usr/local/bin/get-mac-address.sh"""

    map_entry= "        map 00:1a:11:00:00:%02x vhost%d"

    host_entry= """iface vhost%d inet static
            address 10.0.2.%d
            netmask 255.0.0.0
            gateway 10.0.0.1"""

    print header

    first_value= 1
    last_value= 16

    for i in range(first_value, last_value + 1):
        print map_entry % (i, i,)

    print ""

    for i in range(first_value, last_value + 1):
        print host_entry % (i, i,)

SSH Authentication
^^^^^^^^^^^^^^^^^^

Since a guest is accessed a lot like a SSHHost, it must also be
configured for password-less login, for example through public key
authentication.

Serial Console
^^^^^^^^^^^^^^

Altough this is not necessary for Autoserv itself, it is almost
essential to be able to start the guest image with qemu manually, for
example to do the initial setup. Qemu can emulate the display from a
video card but it can also emulate a serial port. In order for this to
be useful, the guest image must be setup appropriately:

-  in the grub config (``/boot/grub/menu.lst``), if you use grub, to
   display the boot menu

   ::

       serial --unit=0 --speed=9600 --word=8 --parity=no --stop=1
       terminal --timeout=3 serial console

-  in the kernel boot options, for boot and syslog output to the console

   ::

       console=tty0 console=ttyS0,9600

-  have a getty bound to the console for login, in ``/etc/inittab``

   ::

       T0:23:respawn:/sbin/getty -L ttyS0 9600 vt100

Running Autotest In a Guest
~~~~~~~~~~~~~~~~~~~~~~~~~~~

Here is an example Autoserv control file to run an Autotest job inside a
guest (virtual machine). This control file is special because it also
runs OProfile on the host to collect some profiling information about
the host system while the guest is running. This uses the system
installation of oprofile, it must therefore be properly installed and
configured on the host. The output of ``opreport`` is saved in the
results directory of the job that is run on the guest.

Here, a single address mapping is specified to kvm, since only one guest
will be spawned. We tried running oprofile inside a kvm guest, without
success, therefore it is not enabled. Finally, the options to
``opcontrol --setup`` should be adjusted if you know that ``vmlinux`` is
present on the host system.

::

    remote_host= hosts.SSHHost("192.168.1.1")

    kvm_on_remote_host= kvm.KVM(remote_host)

    kvm_on_remote_host.get("/var/local/src/kvm-compiled.tar.gz")
    addresses= [{"mac": "02:00:00:00:00:01" , "ip" : "10.0.0.1"}]
    kvm_on_remote_host.install(addresses, build=False, insert_modules=False)

    qemu_options= "-m 256 -hda /var/local/vdisk.img -snapshot"
    g1= hosts.KVMGuest(kvm_on_remote_host, qemu_options)
    g1.wait_up()

    at= autotest.Autotest()
    at.get("/home/foo/autotest/client")
    at.install(g1)

    control_file= """
    #~ job.profilers.add("oprofile", events= ["CPU_CLK_UNHALTED:8000"])
    job.run_test("linus_stress")
    """

    results_dir= "g1_results"

    # -- start oprofile
    remote_host.run("opcontrol --shutdown")
    remote_host.run("opcontrol --reset")
    remote_host.run("opcontrol --setup "
        # "--vmlinux /lib/modules/$(uname -r)/build/vmlinux "
        "--no-vmlinux "
        "--event CPU_CLK_UNHALTED:8000")
    remote_host.run("opcontrol --start")
    # --

    at.run(control_file, results_dir, g1)

    # -- stop oprofile
    remote_host.run("opcontrol --stop")
    tmpdir= remote_host.get_tmp_dir()
    remote_host.run('opreport -l &> "%s"' % (sh_escape(os.path.join(tmpdir, "report")),))
    remote_host.get_file(os.path.join(tmpdir, "report"), os.path.join(results_dir, "host_oprofile"))
    # --

Changing the Guest Kernel
~~~~~~~~~~~~~~~~~~~~~~~~~

"Usual" Way
^^^^^^^^^^^

The kvm virtual machine uses a bootloader, it can be rebooted and kvm
will keep running, therefore, you can install a different kernel on a
guest just like on a regular host:

::

    remote_host= hosts.SSHHost("192.168.1.1")

    kvm_on_remote_host= kvm.KVM(remote_host)
    kvm_on_remote_host.get("/var/local/src/kvm-compiled.tar.gz")
    addresses= [{"mac": "02:00:00:00:00:01" , "ip" : "10.0.0.1"}]
    kvm_on_remote_host.install(addresses, build=False, insert_modules=False)

    qemu_options= "-m 256 -hda /var/local/vdisk.img -snapshot"
    g1= hosts.KVMGuest(kvm_on_remote_host, qemu_options)
    g1.wait_up()

    print g1.run("uname -a").stdout

    kernel= deb_kernel.DEBKernel()
    kernel.get("/home/foo/linux-2.6.21.3-6_2.6.21.3-6_amd64.deb")

    kernel.install(g1)
    g1.reboot()

    print g1.run("uname -a").stdout

"QEMU" Way
^^^^^^^^^^

It is also possible to use the qemu ``-kernel``, ``-append`` and
``-initrd`` options. These options allow you to specify the guest kernel
as a kernel image on the host's hard disk.

This is a situation where DEBKernel's extract() method is useful because
it can extract the kernel image from the archive on the host, without
installing it uselessly. However, .deb kernel images do not contain an
initrd. The initrd, if needed, is generated after installing the package
with a tool like ``update-initramfs``. The tools ``update-initramfs``,
``mkinitramfs`` or ``mkinitrd`` are all designed to work with an
installed kernel, it is therefore very inconvenient to generate an
initrd image for a .deb packaged kernel without installing it. The best
alternative is to configure the guest kernel so that it doesn't need an
initrd, this is easy to achieve for a qemu virtual machine, it is
discussed in the section :doc:`Guest Kernel <Autoserv>`. On
the other hand, if you already have a kernel and its initrd, you can
also transfer them to the host with ``send_file()`` and then use those.

An important thing to note is that even though the kernel image (and
possibly the initrd) are loaded from the host's hard disk, the modules
must still be present on the guest's hard disk image. Practically, if
your kernel needs modules, you can install them by manually starting
qemu (without the ``-snapshot`` option) with the desired disk image and
installing a kernel (via a .deb if you want) for the same version and a
similar configuration as the one you intend to use with ``-kernel``. You
can also keep the ``-snapshot`` option and use the ``commit`` command in
the qemu monitor.

Here's an example control file that uses the qemu ``-kernel`` option. It
gets the kernel image from a .deb, it is a kernel configured not to need
an initrd:

::

    remote_host= hosts.SSHHost("192.168.1.1")

    kvm_on_remote_host= kvm.KVM(remote_host)
    kvm_on_remote_host.get("/var/local/src/kvm-compiled.tar.gz")
    addresses= [{"mac": "02:00:00:00:00:01" , "ip" : "10.0.0.1"}]
    kvm_on_remote_host.install(addresses, build=False, insert_modules=False)

    kernel= deb_kernel.DEBKernel()
    kernel.get("/home/foo/linux-2.6.21.3-6_2.6.21.3-6_amd64-noNeedForInitrd.deb")
    kernel_dir= kernel.extract(remote_host)

    qemu_options= '-m 256 -hda /var/local/vdisk.img -snapshot -kernel "%s" -append "%s"' % (sh_escape(os.path.join(kernel_dir, kernel.get_image_name()[1:])), sh_escape("root=/dev/hda1 ro console=tty0 console=ttyS0,9600"),)

    g1= hosts.KVMGuest(kvm_on_remote_host, qemu_options)
    g1.wait_up()

    print g1.run("uname -a").stdout

Parallel commands
-----------------

Autoserv control files can run commands in parallel via the
``parallel()`` and ``parallel_simple()`` functions from
``subcommand.py``. This is useful to control many machines at the same
time and run client-server tests. Here is an example that runs the
Autoserv netperf2 test, which is a network benchmark. This example runs
the benchmark between a kvm guest running on one host and another
(physical) host. This control file also has some code to check that a
specific kernel version is installed on these hosts and install it
otherwise. This is not necessary to the netperf2 test or to parallel
commands but it is done here to have a known configuration for the
benchmarks.

::

    def check_kernel(host, version, package):
        if host.run("uname -r").stdout.strip() != version:
            package.install(host)
            host.reboot()

    def install_kvm(kvm_on_host_var_name, host, source, addresses):
        exec ("global %(var_name)s\n"
            "%(var_name)s= kvm.KVM(host)\n"
            "%(var_name)s.get(source)\n"
            "%(var_name)s.install(addresses)\n" % {"var_name": kvm_on_host_var_name})

    remote_host1= hosts.SSHHost("192.168.1.1")
    remote_host2= hosts.SSHHost("192.168.1.2")

    kernel= deb_kernel.DEBKernel()
    kernel.get("/var/local/linux-2.6.21.3-3_2.6.21.3-3_amd64.deb")

    host1_command= subcommand(check_kernel, [remote_host1, "2.6.21.3-3", kernel])
    host2_command= subcommand(check_kernel, [remote_host2, "2.6.21.3-3", kernel])

    parallel([host1_command, host2_command])

    install_kvm("kvm_on_remote_host1", remote_host1, "/var/local/src/kvm-33.tar.gz", [{"mac": "02:00:00:00:00:01", "ip" : "10.0.0.1"}])

    qemu_options= "-m 256 -hda /var/local/vdisk.img -snapshot"
    gserver= hosts.KVMGuest(kvm_on_remote_host1, qemu_options)
    gserver.wait_up()

    at= autotest.Autotest()
    at.get("/home/foo/autotest/client")
    at.install(gserver)
    at.install(remote_host2)

    server_results_dir= "results-netperf-guest-to-host-far-server"
    client_results_dir= "results-netperf-guest-to-host-far-client"

    server_control_file= 'job.run_test("netperf2", "%s", "%s", "server", tag="server")' % (sh_escape(gserver.hostname), sh_escape(remote_host2.hostname),)
    client_control_file= 'job.run_test("netperf2", "%s", "%s", "client", tag="client")' % (sh_escape(gserver.hostname), sh_escape(remote_host2.hostname),)

    server_command= subcommand(at.run, [server_control_file, server_results_dir, gserver])
    client_command= subcommand(at.run, [client_control_file, client_results_dir, remote_host2])

    parallel([server_command, client_command])

