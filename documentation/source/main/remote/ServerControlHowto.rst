Writing server-side control files
=================================

Start with the client-side files. It's amazing how much stuff you can do
with them (including reboots, etc). The client-side harness will
communicate back with the server, and monitor status, etc.

However, if you want to do more powerful things, like control a complex
test across a cluster, you'll probably want to use server-side control
files. Read :doc:`Autotest Structure <../general/AutotestStructure>` on how the
server works first, this will help explain things ...

Server-side control files have the same philosophy as the client-side
files, but run on the server, so it's still a Python script, with all
the flexibility that gives you. You should generally name server-side
control files ending in '.srv' - that makes it a lot easier to recognize
server-side control files at a glance.

You run a server-side control file by doing

::

    server/autoserv -m <machine,machine,...> mycontrolfile.srv

We strip out the -m paramater, break up the comma-separated list, and
put that into your namespace as a list called "machines". Any extra
arguments besides the control file name will appear as a list called
"args".

A basic control file
--------------------

A simple one might do something like this:

::

    host = hosts.create_host(machines[0])

    print host.run("uname -a").stdout
    host.reboot()
    print host.run("uname -a").stdout

Firstly we create a "host" object from the machine name. That has lots
of magic helpers for you, and is how you get most stuff done on the
client.

After, the control file runs "uname -a" on the remote host, printing the
output of the command. It then reboots the machine, and re-runs the
"uname -a" command. So you will see what kernel was running on the
machine when the test started, and then you will see whatever the
default kernel is once the machine is rebooting, ending up with output
like:

::

    KERNEL VERSION AT START OF TEST
    DEFAULT KERNEL VERSION

Running some server-side tests
------------------------------

Okay, so now we want to run some actual tests. The easiest kind of test
to run from the server is a server-side test (i.e. something in
server/tests or server/site\_tests). You run it just like you would run
a client-side test from a client-side control file - with job.run\_test.
So you can run a simple sleeptest with:

::

    job.run_test("sleeptest")

This will run sleeptest. However, it's important to remember that when
you run a server-side test then it runs on the server, not on the lis of
machines you pass in on the autoserv command line. For something like a
simple sleep test this doesn't really matter, but in general your test
will need to manually do the setup required to run command remotely;
either by creating it's own host object with create\_host, or by
accepting a host object as a parameter.

Running some client-side tests
------------------------------

OK, so when it comes to running server-side tests we mentioned that you
have make sure your test runs all of its commands through a host object.
But if all your test needs to do is run a bunch of local commands, that
can make things a lot uglier; it would be easier to just run the test
directly on the test machine, like you do with a client-side test.

Fortunately, just using a server-side control file it doesn't mean that
you have use server-side tests; you can write client-side tests like you
normally would and still use a control file from the server-side to do
whatever setup you need to do, then launch the tests on the remote
machine using the Autotest client.

So, supposing we want to run some client-side tests on a remote machine.
What you then need to do is:

-  create a host object with hosts.create\_host
-  create an Autotest object with autotest.Autotest, on the remote host
-  run a client-side control file on the remote host with run (or use
   the run\_test helper for the simple case of running a single test)

You can do this like so:

::

    host = hosts.create_host(machines[0])
    at = autotest_remote.Autotest()(host)
    at.run_test('kernbench', iterations=2)

This will create a host object, create an Autotest object against that
host, and then run the client-side kernbench test on the remote host,
using Autotest. If Autotest is not installed on the remote machine,
using at.run\_test (or at.run) would automatically install it first.
Alternatively, if you need to explicitly control when the installation
of Autotest happens you can call at.install.

For an example of how to use run instead of run\_test, see:

::

    host = hosts.create_host(machines[0])
    at = autotest_remote.Autotest(host)
    control = """\
    job.run_test('kernbench', iterations=5)
    job.run_test('dbench', iterations=5)
    job.run_test('tbench', iterations=5)
    job.run_test('bonnie', iterations=5)
    job.run_test('iozone', iterations=5)
    job.run_test('fsx')
    """
    at.run(control)

This will produce the same effect as if you installed an Autotest client
on the remote machine, created a control file like the one stored in the
'control' variable, and then ran it directly with the bin/autotest
script.

Running other existing server control files
-------------------------------------------

So, sometimes instead of just running a specific test you actually have
a pre-existing suite of tests you want to run. For example, suppose you
have a control file for running a standard suite of fast-running
performance tests that you want to incorporate into a new control file
you're building. You could just look at what tests the existing suite
runs and run them yourself from your new control file, but not only is
that a tedious bunch of cut-and-paste work, it also means that if the
"standard" suite changes you now have to go and update your new script
as well.

Instead of doing that, we can just make use of the job.run\_control
method. This allows you to just run a control file directly from another
control file by passing in a file name. So for example, if on your
server installation you have a test\_suites/std\_quick\_tests control
file, you can execute it from a new one quite simply as:

::

    job.run_control('test_suites/std_quick_tests')

The path you pass is is relative to the Autotest directory (i.e.
job.autodir). Similarly, if you wanted to run the standard sleep test
control file you could do it with:

::

    job.run_control('server/tests/sleeptest/control')

Note that variables from your current execution environment will not
leak into the environment of the executed control file, and vice versa.
So you cannot pass "parameters" into a control file by just setting a
global variable that the executed control file then reads, and you
cannot pass back results to assigning a global in the executed control
file. However, this doesn't mean that the two execution environments are
completely isolated; in particular, the job instance used by the
executing file is the same one used by the executed file. However, as a
general rule control files should avoid developing interdependencies by
modifying the job object to pass information back and forth.

Using more than one machine at once
-----------------------------------

So far all the examples that have run on the remote machine have done so
using hosts.create\_host(machines[0]) to create a Host object. However,
while this is okay for just trying things out it's not a good way to
write a "real" control file; if you run autoserv with a list of
machines, you'll only ever run tests on the first one!

Now, the most obvious thing to do would be to just wrap your machines[0]
in a for loop, but this isn't going to work very well if you run
something against a hundred machines -- it's going to do the runs
sequentially, with 99 of the machines sitting around doing nothing at
any particular point in time. Instead what you want to do is run things
in parallel, like so:

::

    def run(machine):
        host = hosts.create_host(machine)
        at = autotest_remote.Autotest(host)
        at.run_test('kernbench', iterations=5)

    commands = [subcommand(run, args=[machine], subdir=machine) for machine in machines]
    parallel(commands)

What this does is actually simpler than it looks; first, it defines a
runs kernbench on one machine. Then, it defines a list of subcommands,
one for each machine. Finally, it uses parallel to run all these
commands (in parallel, via fork).

If you're familiar with job.parallel on the client, this is somewhat
similar, but more powerful. The job.parallel method represents
subcommands as a list, with the first item being a function run and the
remainder being arguments to pass to it. The subcommand object is
similar, taking a function and a list of args to pass to it.

In addition, subcommand also takes a very useful subdir argument to
allow us to avoid mashing together all the results from each machine in
the same results directory. If you specify subdir to a subcommand, the
forked subcommand will run inside of subdir (creating it if it exists).
So you will end up with three separate kernbench results in three
separate machine subdirectories.

It's important to keep in mind that the final test results parser really
only works well with results directories that are associated directly
with a single machine, so when using parallel to do separate runs on
individual machines you pretty much always want to specify a
subdir=machine argument to your subcommands.

In fact, for this very specific case (running the exact same function on
N machines) we have a special helper method, job.parallel\_simple,
doesn't require as much setup. You could replace the above code with the
simpler:

::

    def run(machine):
        host = hosts.create_host(machine)
        at = autotest_remote.Autotest(host)
        at.run_test('kernbench', iterations=5)

    job.parallel_simple(run, machines)

Synchronous vs Asynchronous jobs
--------------------------------

If you run control files through the frontend, it needs to know how you
want them to be run.

Let's say there's 6 clients we're controlling. We could either run
asynchronously, with a separate autoserv instance controlling each
machine. If you do this, it will kick off separate autoserv instances as
each machine becomes available. We ask for this by specifying
SYNC\_COUNT=1

::

    autoserv control_file -m machine1
    autoserv control_file -m machine2
    autoserv control_file -m machine3
    autoserv control_file -m machine4
    autoserv control_file -m machine5
    autoserv control_file -m machine6

Or we can run synchronously. If you do that, we'll wait for \*all\* the
machines you asked for before starting the job, and do something like
this:

::

    autoserv control_file -m machine1,machine2,machine3,machine4,machine5,machine6

Often we only need to pair up machines (say 1 client and 1 server to run
a network test). But we don't want to wait for all 6 machines to be
available; as soon as we have 2 ready, we might as will kick those off.
We can use SYNC\_COUNT to specify how many we need at a time, in this
case SYNC\_COUNT=2. We'll end up doing something like this:

::

    autoserv control_file -m machine1,machine2
    autoserv control_file -m machine3,machine4
    autoserv control_file -m machine5,machine6

Installing kernels from a server-side control file
--------------------------------------------------

So, if you've written a client-side control file for installing a
kernel, you're probably familiar with code that looks something like:

::

    testkernel = job.kernel('/usr/local/mykernel.rpm')  
    testkernel.install()
    testkernel.boot()

This will install a client on the local machine. Well, we've also seen
that in a server-side control file, unless you use a Host object to run
commands then your operations run on the server, not your test
machine(s). So just trying to use the same code won't work.

However, we've already seen that you can use an Autotest object to run
arbitrary client-side control files on a remote machine. So you can
instead use some code like this:

::

    kernel_install_control = """
    def step_init():
        job.next_step([step_test])
        testkernel = job.kernel('/usr/local/mykernel.rpm')
        
        testkernel.install()
        testkernel.boot()

    def step_test():
        pass
    """

    def install_kernel(machine):
        host = hosts.create_host(machine)
        at = autotest_remote.Autotest(host)
        at.run(kernel_install_control, host=host)
    job.parallel_simple(install_kernel, machines)

This will install /usr/local/mykernel.rpm on all the machines you're
running your test on, all in parallel. You can then follow up this code
in your control file with the code to run your actual tests.
