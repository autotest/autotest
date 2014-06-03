===============================
Conmux - Original Documentation
===============================

conmux, the console multiplexor is a system designed to abstract the
concept of a console. That is to provide a virtualised machine
interface, including access to the console and the 'switches' on the
front panel; the /dev/console stream and the reset button. It creates
the concept of a virtual console server for multiple consoles and
provides access to and sharing of consoles connected to it.

There are two main motivations for wanting to do this. Firstly, we have
many different machine types with vastly differing access methodologies
for their consoles and for control functions (VCS, HMC, Annex) and we
neither want to know what they are nor how they function. Secondly, most
console sources are single access only and we would like to be able to
share the console data between many consumers including users. Basic
Usage

The main interface to the consoles is via the console program. This
connects us to the console server for the machine and allows us to
interact with it, including issuing out-of-band commands to control the
machine.

::

    $ console <host>/<console>

In the example below we indicate that the console we require is located
on the virtual console server consoles.here.com and the specific console
is elm3b70.

::

    $ console consoles.here.com/elm3b70 
    Connected to elm3b70 console (~$quit to exit) Debian GNU/Linux 3.1 elm3b70 ttyS0 
    elm3b70 login:

Once connected we can interact normally with the console stream. To
perform front pannel operation such as peforming an hard reset we switch
to command mode. This is achieved using the escape sequence ~$. Note the
prompt Command>

::

    elm3b70 login: ~$
    Command> quit
    Connection closed $

Command Summary
---------------

The following commands are generally available:

+-------------+------------------------------------------------------------------------------------------------------------------------------------+
| Command     | Description                                                                                                                        |
+-------------+------------------------------------------------------------------------------------------------------------------------------------+
| quit        | quit this console session, note that this disconnects us from the session it does not affect the integity of the session itself.   |
+-------------+------------------------------------------------------------------------------------------------------------------------------------+
| hardreset   | force a hard reset on the machine, this may be a simple reset or a power off/on sequence whatever is required by this system.      |
+-------------+------------------------------------------------------------------------------------------------------------------------------------+

Architecture
------------

The conmux provides a virtual console multiplexor system reminicent of
an Annex terminal server. You refer to the conmux server and lines,
unlike an Annex lines are referred to by mnemonic names. Above we
referred to the console for elm3b70 'connected to' the server
consoles.here.com. A virtual console server consists of a number of
server processes. One conmux-registry server, several conmux servers and
optionally several helper processes.

conmux-registry: a server is defined by the server registry. This
maintains the mnemonic name to current server location relation. When a
client wishes to attach to a console on a server, the registry is first
queried to locate the server currently handling that console.

conmux: for each connected console there is a corresponding console
multiplexor. This process is responsible for maintaining the connection
to the console and for redistributing the output to the various
connected clients. It is also responsible for handling "panel" commands
from the client channels.

autoboot-helper: an example helper which aids systems which are not
capable of an automatic reboot. It connects to a console and watches for
tell-tale reboot activity, preforming a "panel" hardreset when required.
This provides the impression of seamless reboot for systems which this
does not work. Configuration conmux-registry

Configuration of this service is very simple. Supplying the default
registry port (normally 63000) and the location for the persistant
registry database. conmux

Configuration of each conmux is complex. Each has a listener, payload
and optionally one or more panel commands. Configuration is provided via
a per console configuration file. This file consists of lines defining
each element:

::

    listener <server>/<name>: defines the name of this console port as it appears in the registry.

    socket <name> <title> <host>:<port>: defines a console payload connected to a tcp socket on the network. name defines this payload within the multiplexor, title is announced to the connecting clients.

    application <name> <title> <cmd>: defines a console payload which is accessed by running a specific command. name defines this payload within the multiplexor, title is announced to the connecting clients.

    command <panel> <message> <cmd>: defines a panel command for the preceeding payload, triggerd when panel is typed at the command prompt. message is announced to the user community. cmd will be actually executed.

For example here is the configuration for a NUMA-Q system which is
rebooted using a remote VCS console and for which the real console
channel is on an Annex terminal server:

::

    listener localhost/elm3b130 
    socket console 'elm3b130 console' console.server.here.com:2040 
    command 'hardreset' 'initated a hard reset' \ './reboot-numaq vcs 1.2.3.4 elm3b130 12346 Administrator password' 

