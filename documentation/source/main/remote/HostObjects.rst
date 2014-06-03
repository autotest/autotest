================
The Host classes
================

There are six main classes in the Host hierarchy, with two concrete
classes that can be instantiated; one that uses the OpenSSH binary for
executing commands on a remote machine, and one that uses the Paramiko
module to do the same. The specific classes are:

-  ``Host`` - the top-level abstract base class, contains definitions
   for most of the standard Host methods, as well as implementations for
   some of the high-level helper methods.
-  ``RemoteHost`` - a subclass of ``Host`` that also adds some options
   specific to "remote" machines, such as having a hostname, as well as
   providing generic reboot and crashinfo implementations.
-  ``SiteHost`` - a subclass of ``RemoteHost`` that allows you to hook
   site-specific implementation behavior into your ``Host`` classes.
   This may not even be defined (in which case we automatically default
   to providing a empty definition) but can be used to insert hooks into
   any methods you need. And example of such a use would be adding a
   machine_install implementation that takes advantage of your local
   installer infrastructure and so isn't suitable for inclusion into the
   core classes.
-  ``AbstractSSHHost`` - a subclass of ``SiteHost``, this provides most
   of the remaining implementation needed for using ssh-based
   interaction with a remote machine such as the ability to copy files
   to and from the remote machine as well as an implementation of the
   various wait_* methods
-  ``SSHHost`` - one of the concrete subclasses of ``AbstractSSHHost``,
   this class can be directly instantiated. It provides an
   implementation of Host.run based around using an external ssh binary
   (generally assumed to be OpenSSH). This is also currently the default
   implementation used if you're using the factory to create the method
   rather than creating Host instance directly.
-  ``ParamikoHost`` - the other concrete subclass of
   ``AbstractSSHHost``. This class provides a lower-overhead,
   better-integrated alternative to the ``SSHHost`` implementation, with
   some caveats. In order to use this class directly you'll need to
   explicitly create an instance of the class, or use custom hooks into
   the host factory. Note that using this class also requires that you
   have the paramiko library installed, as this module is not included
   in the Python standard library.

Creating instances of Host classes
----------------------------------

The concrete host subclasses (``SSHHost, ParamikoHost``) can both be
instantiated directly, by just creating an instance. Both classes accept
hostname, user (defaults to root), port (defaults to 22) and password
(nothing by default, and ignored if connecting using ssh keys). So the
simplest way to create a host is just with a piece of code such as:

::

    from autotest_lib.server.hosts import paramiko_host

    host = paramiko_host.ParamikoHost("remotemachine")

However, there are several disadvantages to this method. First, it ties
you to a specific SSH implementation (which you may or may not care
about). Second, it loses out on support for the extra mixin Host classes
that Autotest provides. So the preferred method for creating a host
object is:

::

    from autotest_lib.server import hosts

    host = hosts.create_host("remotemachine")

The create_host function passes on any extra arguments to the core host
classes, so you can still pass in user, port and password options. It
also accepts additional boolean parameters, auto_monitor and
netconsole.

If you use create_host to build up your instances, it also mixes in
some extra monitoring classes provided by Autotest. Specifically, it
mixes in ``SerialHost`` and/or ``LogfileMonitorMixin``, depending on
what services are available on the remote machine. Both of these classes
provide automatic capturing and monitoring of the machine (via
``SerialHost`` if the machine has a serial console available via conmux,
via monitoring of /var/log/kern.log and /var/log/messages otherwise). If
netconsole=True (it defaults to False) then we will also enable and
monitor the network console; this is disabled by default because network
console can interact badly with some network drivers and hang machines
on shutdown.

If for some reason you want this monitoring disabled (e.g. it's too
heavyweight, or you already have some monitoring of the host via
alternate machines) then it can still be disabled by setting
auto_monitor=False. This allows you to still use create_host to
automatically select the appropriate host class; by default this still
just uses ``SSHHost``, but in the future it may change. Or, your server
may be using custom site hooks into create_host which already change
this behavior anyway.

Custom hooks in create_host
----------------------------

You can optionally define a site_factory.py module with a
postprocess_classes function. This takes as its first parameter a list
of classes that will be mixed together to create the host instance, and
then a complete copy of the args passed to create_host. This function
can then modify the list of classes (in place) to customize what is
actually mixed together. For example if you wanted to default to
``ParamikoHost`` instead of ``SSHHost`` at your site you could define a
site function:

::

    from autotest_lib.server.hosts import ssh_host, paramiko_host

    def postprocess_classes(classes, **args):
        if ssh_host.SSHHost in classes:
            classes[classes.index(ssh_host.SSHHost)] = paramiko_host.ParamikoHost

This will change the factory to use ``ParamikoHost`` by default instead.
Or you could do other changes, for example disabling ``SerialHost``
completely by removing it from the list of classes. Or you could do
something even more complex, like using ``ParamikoHost`` if a host
supports it and falling back to ``SSHHost`` otherwise. Adding additional
args to postprocess_classes is also an option, to add more
user-controllable host creation, but keep in mind that such extensions
can then only be used in site-specific files and tests.

Paramiko vs OpenSSH
-------------------

Why do we provide two methods of connecting via ssh at all? Well, there
are a few advantages and disadvantages to both.

Why openssh?
------------

If we use openssh then we generally have more portability and better
integration with the users configuration (via ssh_config). This is also
more configurable in general, from an external point of view, since a
user can customize ssh behavior somewhat just by tweaking ~/.ssh/config

So why paramiko?
----------------

However, there are also limitations that come up with openssh. It mostly
operates as a black box; all we can do to detect network- or ssh-level
issues is to watch for a 255 exit code from ssh, and to attempt to break
things down into authentication issues versus various connection issues
we have to try and parse the output of the program itself, output which
may be mixed in with the output of the remote command.

There can also be performance issues when openssh is in use, due to the
large number of processes that can end up being spawned to run ssh
commands; even if most of this memory is cached and shared the memory
costs start to pile up. Additionally the cost of creating new
connections for every single ssh command can start to pile up.

Paramiko alleviates these problems by moving the ssh handler in-process
as a python library, and taking advantage of the multi-session support
in SSH protocol 2 to run multiple commands over a single persistent
connection. However, it has the cost of requiring that you use a
protocol 2 sshd on the remote machine, and requires installing the
paramiko library. It also has much weaker support for ssh_config, with
some support for finding keyfiles (via IdentityFile?) and nothing else.

Setting up ParamikoHost
---------------------------

There are two main issues you need to resolve to use ParamikoHost,
1) installing paramiko and 2) making sure you have support for protocol
2 connections.

Point one is fairly straightforward, just refer to one of the bullet
points in :doc:`autotest server install <../sysadmin/AutotestServerInstall>`
that explains how to install paramiko.

Point two is a bit more complex. There's a fairly good chance your
infrastructure already supports protocol 2, since it's been around for
quite a long time now and is generally considered to be the standard. To
test it, just try connecting to a machine via ssh using the
``-o Protocol=2`` option; if it succeeds then ``ParamikoHost`` should
just work once the point one is taken care of. If it fails with an error
message about protocol major version numbers differing, then you're in
trouble; you'll need to reconfigure sshd on your remote machines to
support protocol 2, and if you're using key-based authentication you'll
need to add support for protocol 2 keys as well. If these configuration
changes are not practical (either for technical or organizational
reasons) then you'll simply have to forgo the use of ``ParamikoHost``.

Standard Methods
----------------

The Host classes provide a collection of standard methods for running
commands on remote machines, copying files to and from them, and
rebooting them (for remote machines).

Host.run
--------

This method can be used to run commands on a host via an interface like
that of the run function in the utils module. It returns a CmdResult?
object just like utils.run, and supports the ignore_status, timeout and
std*_tee methods with the same semantics.

Host.send_file, Host.get_file
-------------------------------

These methods allow you to copy file(s) and/or directory(s) to a remote
machine. You can provide a single path (or a list of paths) as a source
and a destination path to copy to, with send_file for destinations on
the host and get_file for sources on the host. The pathname semantics
are intended to mirror those of rsync so that you can specify "the
contents of a directory" by terminating the path with a /.

Host.reboot, Host.reboot_setup, Host.reboot_followup, Host.wait_up, Host.wait_down
--------------------------------------------------------------------------------------

The reboot method allows you to reboot a machine with a few different
options for customizing the boot:

-  timeout - allows you to specify a custom timeout in seconds. Used
   when you want reboot to automatically wait for the machine to restart
   (the default). If the reboot takes longer than *timeout* seconds to
   come back after shutting down then an exception will be thrown.
-  label - the kernel label, used to specify what kernel to boot into.
   Defaults to host.LAST_BOOT_TAG which will reboot into whatever
   kernel the host was last booted into by Autotest (or the default
   kernel if Autotest has not yet booted the machine in the job).
-  kernel_args - a string of extra kernel args to add to the kernel
   being booted, defaults to none (which means no extra args will be
   added)
-  wait - a boolean indicating if reboot should wait for the machine to
   restart after starting the boot, defaults to true. If you set this to
   False then if you try to run commands against the Host it'll just
   time out and fail, and the reboot_followup method won't be called.
-  fastsync - if True (default is False) don't try to sync and wait for
   the machine to shut down cleanly, just shut down. This is useful if a
   faster shutdown is more important than data integrity.
-  reboot_cmd - an optional string that lets you specify your own
   custom command to reboot the machine. This is useful if you want to
   specifically crank up (or turn down) the harshness of the shutdown
   command.

In addition to reboot, there are two hooks (reboot_start and
reboot_followup) that are called before and after the reboot is run.
This allows you to define mixins (like ``SerialHost`` and some other
classes we'll mention later) that can hook into the reboot process
without having to implement their own reboot.

Finally, there are wait_down and wait_up methods, specifically for
waiting for a rebooting machine to shut down or come up. If you use the
reboot method these should generally be only used internally, but you
can use them yourself directly if you need more custom control of the
powering up and/or down of the machine.

