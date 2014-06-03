=======================
Autoserv Client Install
=======================

When you install an Autotest client from a server side control file,
either manually using ``Autotest.install`` or automatically when running
a client control file using autoserv, autoserv has to determine a
location on the remote host to install the client.

If you need the client installed in a specific location then the most
direct solution is to pass in an ``autodir`` parameter to
``Autotest.install`` since this will disable any automatic determination
and just use the provided path. However in the case that this is not
possible or practical then the following sources are checked for a path
and the first one found is used:

#. The result of calling ``Host.get_autodir`` if it returns a value
#. The dirname of the target of the ``/etc/autotest.conf`` symlink on
   the remote machine
#. ``/usr/local/autotest`` if it exists on the remote machine
#. ``/home/autotest`` if it exists on the remote machine
#. ``/usr/local/autotest`` even if it doesn't exist

Note that an Autotest client install will itself call
``Host.set_autodir`` to set it to the install location it ended up
using.

