=================
Autotest Test API
=================

This is a review of the available autotest test API.

Control files
-------------

A control file is just python code, and therefore should follow the
Autotest python style. The control file ultimately defines the test. In
fact the entire test can be coded in the control file. However if this
leads to a very complicated control file, it is generally recommended
that most of the test code logic be placed in a python module that the
control file runs (via the job object).

A control file should define at the very top a set of variables. These
are:

-  AUTHOR
-  TIME
-  NAME
-  TEST\_CATEGORY
-  TEST\_CLASS
-  TEST\_TYPE
-  SYNC\_COUNT
-  DOC

All except SYNC\_COUNT are set to a string. SYNC\_COUNT is a number
which has relevance for the scheduling of multi-machine server side
jobs. In addition you can define the variable EXPERIMENTAL (either True
or False). By default it is False, but when set to True, will control
whether the job shows up in the web frontend by default.

Unlike python test code, it is not imported, but rather is executed
directly with the exec() method in the context of certain global and
local symbols. One of the symbols that your control file can assume
exists is *job*. The *job* object has a number of methods that you will
most probably use in your control file. The most common are

-  *job.run\_test(test\_object, tag, iterations, constraints,
   **dargs)*******
-  *job.parallel\_simple(run\_method, machine\_list)*
-  *job.record(status\_code, subdir, operation, status)*

In addition, the control file has access to *machines* which is a list
of the machines that were passed to the autoserv executable.

Client side tests
-----------------

A client side test runs entirely on the client (or host machine).
Essentially the entire client subdirectory of Autotest is installed on
the host machine at the beginning of the test. And so the client control
file through the job.run\_test() method can execute code contained in a
test class. A test class is code that is generally located in either a
subdirectory of client/tests/ or client/site\_tests/. A test class
always is a subclass of *autotest\_lib.client.bin.test.test*. You then
must provide an override for the *run\_once()* method in your class. You
must also define the class variable *version*. The *run\_once* method
can accept any arguments you desire. These are passed in as the
***dargs*****in the *job.run\_test()* method in the control file.**

In addition to *run\_once()* you may optionally override the following
methods

-  *initialize()*
-  *setup()*
-  *warmup()*
-  *run\_once()*
-  *postprocess()*

The *initialize* is called first every time the test is run. The *setup*
method is called once if the test version changed. Then the *warmup* is
called once. After this run\_once is called *iterations* times. Finally
*postprocess* is called. The arguments that each method take are
arbitrary. The ***dargs*****from *run\_test()* are simply passed
through. The exception being *postprocess* which takes no arguments
(other than self of course).**

The *autotest\_lib.client.bin.test.test* class also defines various
useful variables. These are

-  *job*: the job object from the control file
-  *autodir*: the autotest directory
-  *outputdir*: the output directory
-  *resultsdir*: the results directory
-  *profdir*: the profiling directory
-  *debugdir*: the debugging directory
-  *bindir*: The bin directory
-  *srcdir*: the src directory
-  *tmpdir*: the tmp directory

In addition the test object has a handful of very useful methods

-  *write\_test\_keyval(attr\_dict)*
-  *write\_perf\_keyval(perf\_dict)*
-  *write\_attr\_keyval(attr\_dict)*
-  *write\_iteration\_keyval(attr\_dict, perf\_dict)*

The test keyvals are key/attribute pairs that are associated with the
test. You supply a dictionary, and these will be recorded in a test
level keyvals file as well as in the results (tko) database. The
iteration keyvals can be either performance metrics (a number) or an
attribute (a string). They can be recorded for each iteration, and you
can either record one, the other, or both with the latter three methods
above.

In addition the test class at the end of each iteration will evaluate
any constraints that have been passed into the test via the
job.run\_test() command. The constraints variable is a list of strings,
where each string makes an assertion regarding an iteration keyval.
These are evaluated, and failures are recorded. An example constraints
might be: *constraints = ['throughput > 6500', 'test\_version == 2']*

Generally a typical client side test will make use of code contained in
the standard python libraries, as well as the various utilities located
in *autotest\_lib.client.bin.utils*.

Server side tests
-----------------

In a typical server side test, the autotest client is not installed on
the host machines. Rather the server keeps host objects that represent
an ssh connection to the host machine, and through which the server can
execute code on the clients. A host object is generally created in the
following way

::

    host = hosts.create_host(machine)

The *hosts* module is one of those symbols that you can safely assume is
present in your server control file. The machine is a machine name, and
is generally one of the list *machines* which is also assumed to be
accessible from your control file.

A typical server control file might look like

::

    def run(machine):
        host = hosts.create_host(machine)
        ...

    job.parallel_simple(run, machines)

In the above code, the *job.parallel\_simple()* takes the list of
*machines* and a method, and executes that method for each member of
*machines*. The first line of the *run* method creates a *host* object
that the server can use to execute commands (via ssh) on the client. A
*host* object has various member variables:

-  *hostname*
-  *autodir*
-  *ip*
-  *user*
-  *port*
-  *password*
-  *env*
-  *serverdir*

Running code on a client can be done via the host object. Typical
methods of a *host* object are:

-  *run(cmd)*
-  *run\_output(cmd, \*args, **dargs)*******
-  *reboot()*
-  *sysrq\_reboot()*
-  *get\_file(src, dest, delete\_dest=False)*
-  *send\_file(src, dest, delete\_dest=False)*
-  *get\_tmp\_dir()*
-  *is\_up()*
-  *is\_shutting\_down()*
-  *wait\_up(timeout=None)*
-  *wait\_down(timeout=None)*
-  *ssh\_ping(timeout=60)*

A large number of other methods are available and are scattered
throughout the code in server/hosts/. The host object that is created by
the hosts.create\_host() method is a mix-in of various host behaviours
that are defined in the server/hosts directory. However the most common
are defined above.

In addition to methods on host, we can run client code via our server
control file using an Autotest object. In order to use the autotest
module you must import if from *autotest\_lib.server*. A typical usage
is

::

    from autotest_lib.server import autotest

    control_file = """job.run_test('sleeptest')"""

    def run(machine):
        host = hosts.create_host(machine)
        at = autotest.Autotest(host)
        at.run(control_file, machine)


    job.parallel_simple(run, machines)

The *autotest* object will (as part of its instantiation) install the
autotest client on the host. Then we can use the *run* method to run
code on the client. The first argument is a string. We could have just
as easily written

::

    at.run(open("some control file").read(), machine))

as well.

Multi-machine server side tests
-------------------------------

The power of server side tests, is their ability to run different code
on multiple machines simultaneously, and to control their interactions.
The easiest way to describe a multi-machine test is to look at a real
example of one. The following control file is located in
server/tests/netperf2/control.srv

::

    AUTHOR = "mbligh@google.com (Martin Bligh) and bboe@google.com (Bryce Boe)"
    TIME = "SHORT"
    NAME = "Netperf Multi-machine"
    TEST_CATEGORY = "Stress"
    TEST_CLASS = 'Hardware'
    TEST_TYPE = "Server"
    SYNC_COUNT = 2
    DOC = """
    ...
    """

    from autotest_lib.server import utils, autotest

    def run(pair):
        server = hosts.create_host(pair[0])
        client = hosts.create_host(pair[1])

        server_at = autotest.Autotest(server)
        client_at = autotest.Autotest(client)

        template = ''.join(["job.run_test('netperf2', server_ip='%s', client_ip=",
                            "'%s', role='%s', test='TCP_STREAM', test_time=10,",
                            "stream_list=[1,10])"])

        server_control_file = template % (server.ip, client.ip, 'server')
        client_control_file = template % (server.ip, client.ip, 'client')

        server_command = subcommand(server_at.run,
                                    [server_control_file, server.hostname])
        client_command = subcommand(client_at.run,
                                    [client_control_file, client.hostname])

        parallel([server_command, client_command])


    # grab the pairs (and failures)
    (pairs, failures) = utils.form_ntuples_from_machines(machines, 2)

    for failure in failures:
        job.record("FAIL", failure[0], "netperf2", failure[1])

    # now run through each pair and run
    job.parallel_simple(run, pairs, log=False)

The top of the file contains the usual control variables. The most
important one is *SYNC\_COUNT*. This test is a 2 machine test. The first
code that runs, is the line

::

    (pairs, failures) = utils.form_ntuples_from_machines(machines, 2)

This code uses a method from *autotest\_lib.server.utils* which given
the full collection of *machines*, forms a list of *pairs* of machines,
and a list of 'failures'. These failures will ,in this case, be at most
a single machine (odd man out). The next line merely uses the *job*
object to record a failure for each of the failures. After this, we call
*job.parallel\_simple()* passing in the run function and the list of
pairs.

The run function defined above takes a pair (recall the function
referenced in *job.parallel\_simple()* takes a single element from the
list that is passed in. In this case it is a single pair). We then
create a host object for each of the machines in the pair. Then we
create an autotest object for each host. A control file string is then
constructed for each of the machines. In this test one host acts as a
client, while the other acts as a server in a network test between the
two hosts. So in this test server does not refer to the autotest server,
but rather to one of the autotest clients running this two machine test.

The next three lines are new. The *subcommand* class, and the *parallel*
method are defined in *autotest\_lib.server* and are assumed to be part
of the control files namespace. The constructor to subcommand requires a
method, and list of args to pass to that method

::

    server_command = subcommand(server_at.run, [server_control_file, server.hostname])

Here the method is the *run* method of one of the autotest objects
created earlier, and we are passing that method the
server\_control\_file, and the hostname. We form the two subcommands
(one for the netperf test server and the other for the netperf test
client). We pass these both to the *parallel()* method as a list. This
method executes both subcommands simultaneously.

The server netperf2 test whose control file is described above, makes
use of the client side netperf2.py test file. This is located in
client/tests/netperf2/netperf2.py. This code is resident on the host
machines by virtue of the creation of the autotest objects. If you take
a look at the *run\_once* method of the netperf2 class, you will see how
it is that we synchronize the running of the client and server sides of
the netperf2 test. The relevant code is

::

    ...
    server_tag = server_ip + '#netperf-server'
    client_tag = client_ip + '#netperf-client'
    all = [server_tag, client_tag]
    ...
    if role == 'server':
        ...
        self.job.barrier(server_tag, 'start_%d' % num_streams, 600).rendevous(*all)
        ...
    else if role == 'client':
        ...
        self.job.barrier(client_tag, 'start_%d' % num_streams, 600).rendevous(*all)
        ...

The above demonstrates how we can synchronize clients. In the above we
register two tags (one for each of two roles). Recall that one of the
hosts is running as the client, while the other is running as the
server. We then form a list of the two tags. The next code segment is
important. If we are the server, we employ the job object that every
test has a reference to, and use it to construct a barrier object using
the *server\_tag*. This says we are registering at the barrier using the
*server\_tag* as our tag, and additionally we pass in 600 seconds as our
timeout. The second argument is a logging string. We then call the
*rendevous* method of the barrier object (yes it is mis-spelled in the
code) and pass in *\*all*. This says that we will wait until all the
tags in the *all* list register. The client side of the code does the
complementary thing. The *rendevous* method blocks until both the
*server\_tag* and the *client\_tag* register. Using these barriers, we
can sync the client and server.

