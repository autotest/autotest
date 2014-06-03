===========================
Autotest Server Quick Start
===========================

You can use the autoserv program located in the server directory of the
Autotest tree to run tests on one or more remote machines. The machines
must be configured so that you can ssh to them without being prompted for a
password.

A simple example is running the sleeptest on a remote machine. Say you
have two machines: On one you have installed the Autotest code (which
will be referred to as the server), and the other is a machine named
mack (which will be referred to as the client).

Then you can run sleeptest on the client. Go to the top of the autotest
tree:

::

    server/autotest-remote -m mack -c client/tests/sleeptest/control

This will result in quite a bit of activity on the screen. Perhaps we
log too much, but you will definitely know that something is happening.
After some time the output should stop and if all went well you will see
that the results directory is now full of files and directories. Before
explaining that, first lets dissect the command above. The "-m" option is
followed by a comma delimited list of machine names (clients) on which
you wish to run your test. The "-c" option tells autoserv that this
is a client side test you are running. And the last argument is the
control file you wish to execute (in this case the sleeptest control
file).

The results directory will generally contain a copy of the control file
that is run (named control.srv). There will also be a keyval file and a
status.log file. In addition there will be a debug/ directory, and a
sysinfo/ directory along with a directory for each client machine (in
this case a mack/ directory). The results of the test are located in the
directories named for each client.

A server side control file allows the possibility of running a test that
involves two or more machines interacting. An example of a server side
multi-machine control file is server/tests/netperf2/control.srv. This
control file requires 2 or more client machines to run. An example of
how to use autoserv follows

::

    server/autotest-remote -m mack,nack -s server/tests/netperf2/control.srv

In this example we are again running the command from the results/
directory. Here we see the "-s" option which specifies this as a
server side control file. We have specified two machines using the "-m"
option (mack and nack). The command should produce a flurry of activity.
Afterwards you can explore the contents of the results directory to see
the results. Of special note will be the contents of the
mack/netperf2/results/keyval and nack/netperf2/results/keyval files. One
of these files will list various performance metrics acquired by the
netperf test.
