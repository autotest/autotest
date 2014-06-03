==========================
Installing a Conmux Server
==========================

This document will explain how to install a conmux server starting from
the Autotest codebase. A rudimentary configuration for an example
console will also be provided

Installing the conmux server
----------------------------

This assumes that you already have a freshly sync'd version of Autotest
as defined in: `Downloading The Source <../DownloadSource>`_ or
that you are using one of the release tarballs. A lot of this is covered
in the
`autotest/conmux/INSTALL <https://github.com/autotest/autotest/blob/master/conmux/INSTALL>`_
file.

Required perl modules:

-  IO::Multiplex;

   -  Debian/Ubuntu? Packages: libio-multiplex-perl
   -  Fedora Packages: perl-IO-Multiplex

Installing IO::Multiplex via CPAN:

::

    perl -MCPAN -e 'install IO::Multiplex'

Building
--------

This section describes how to get the conmux system in to the place you
want it installed on your system. The default location is
/usr/local/conmux

To make and install this package to the default location

::

    make install

To an alternative location:

::

    make PREFIX=/usr/alt/conmux install

To build for a specified prefix, but installed into a temporary tree:

::

    make PREFIX=/usr/alt/conmux BUILD=build/location install

Console configuration
---------------------

This will walk through some configurations for consoles in conmux. Each
configuration has a listener, payload and optionally one or more panel
commands. Configuration is provided via a per console configuration
file.

-  All configurations are stored in BASE\_INSTALL/etc with a .cf
   extension (e.g. dudicus.cf)

listener::

    **listener server/name** defines the name of this console port as it
    appears in the registry.

payload::

    **socket name title host:port** defines a console payload connected
    to a tcp socket on the network. name defines this payload within the
    multiplexor, title is announced to the connecting clients.

    **application name title cmd** defines a console payload which is
    accessed by running a specific command. name defines this payload
    within the multiplexor, title is announced to the connecting
    clients.

command panel::

    **command panel message cmd** defines a panel command for the
    preceeding payload, triggered when panel is typed at the command
    prompt. message is announced to the user community. cmd will be
    actually executed.

Example Config
--------------

A conmux configuration using a socket to connect to the console

::

    listener localhost/dudicus
    socket console 'dudicus' '192.168.0.3:23'

Example with an application:

A very basic example of starting an application (which could be any
application including ones that connect to a proprietary protocol). This
is more just to show how this feature would be used.

::

    listener localhost/cat
    application console 'cat' '/bin/cat'

Not that in the above examples the listener is set to *localhost*. That
states that the localhost is where the consoles are started and where
the conmux\_registry exists. If you are running lots of consoles you may
want to have one central registry and a number of different machines
providing access to them if that were the case you would want to set
localhost to the hostname where the conmux registry is running.

Conmux configuration with hardreset
-----------------------------------

Adding a hardreset command, if you aren't familiar with the Autotest
Hardreset please refer to that for terminology. There are a number of
different expect scripts/python pexect scripts available in
conmux/lib/drivers (on the installed server) each one of these connects
to an RPM in their own way. A unified solution is being worked on but it
is low priority. Basically the customer needs to give you the
information required as outlined in the hardreset documentation and then
you identify which script to use by connecting to the RPM and looking
for brandings like SENTRY or CITRIX etc.

::

    listener localhost/dudicus
    socket console 'dudicus' '192.168.0.3:23'
    command 'hardreset' 'initiated a hard reset' 'reboot-cyclades 192.168.0.12 48 user password 5'

Conmux doesn't really care what it is calling here it is just a program
with parameters, to understand how to use the reboot-cyclades driver you
need to actaully open up the file and read it.

**Generic command** Below is an example of a generic command. Commands
are issued using the ~$ escape sequence and then the command name. An
example of a useful command would be one to show the configuration of
the console you are connected to:

Add the following to your config.cf file:

::

    "command 'config' 'Show conmux configuration' 'cat /home/conmux/etc/dudicus.cf'

Example output:

::

    [/usr/local/conmux/bin]$./console netcat
    Connected to netcat [channel transition] (~$quit to exit)

    Command(netcat)> config
    (user:me) Show conmux configuration
    listener localhost/netcat
    socket console 'netcat' 'localhost:13467'
    command 'config' 'Show conmux configuration' 'cat /usr/local/conmux/etc/netcat.cf'

Starting the Conmux Server
--------------------------

Conmux comes with a bash script that will do the following

-  Start the conmux registry
-  Start all configurations in BASE\_INSTALL/etc that end with .cf
   prefixes
-  Restart consoles that died since the last start command
-  Restart consoles whose configuration has changed since the last start
   command
-  Log console output in BASE\_INSTALL/log

To start the conmux registry and all the consoles issue the following
command

::

    BASE_INSTALL/sbin/start

*Example output:*

::

    /usr/local/conmux/sbin/start
    starting registry ...
    starting CONSOLE1 ...
    starting CONSOLE2 ...

Mock Console Setup using nc
---------------------------

After following all of the above this section provides a concrete
example for users who do not currently have access to any console
hardware. In this section a configuration will be setup for a console on
localhost. Netcat will be used on the machine to listen to the port for
a connection so that an actual console connection can be created.

The configuration:

*etc/netcat.cf*

::

    listener localhost/netcat
    socket console 'netcat' 'localhost:13467'
    command 'config' 'Show conmux configuration' 'cat /usr/local/conmux/etc/netcat.cf'

Start netcat in a different terminal listening on port 13467

::

    nc -l -p 13467

Start your conmux server

::

    BASE_INSTALL/sbin/start

Now connect to the console:

::

    BASE_INSTALL/bin/console netcat

Output should be similar to:

::

    /usr/local/conmux/bin]$./console netcat
    Connected to netcat [channel connected] (~$quit to exit)

If you start typing in here you will notice in the terminal where netcat
is running what you typed and vice versa.

You can also issue the *config* command by using ~$ and inputting
*config*

