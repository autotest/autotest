====================
Client Control files
====================
The key defining component of a job is its *control file*; this file
defines all aspects of a jobs life cycle. The control file is a Python
script which directly drives execution of the tests in question.

Simple Jobs
-----------
You are automatically supplied with a *job object* which drives the job
and supplies services to the control file. A control file can be as
simple as::

    job.run_test('kernbench')

The only mandatory argument is the name of the test. There are lots of
examples; each test has a sample control file under
``tests/<testname>/control``

If you're sitting in the top level of the Autotest client, you can run
the control file like this::

    $ client/autotest-local <control_file_name>

You can also supply specific arguments to the test ::

    job.run_test('kernbench', iterations=2, threads=5)

-  First paramater is the test name.
-  The others are arguments to the test. Most tests will run with no
   arguments if you want the defaults.

If you would like to specify a tag for the results directory for a
particular test::

    job.run_test('kernbench',  iterations=2, threads=5, tag='mine')

Will create a results directory "kernbench.mine" instead of the default
"kernbench". This is particularly important when writing more complex
control files that may run the same test multiple times, in order to
properly separate the results of each of the test runs they will need a
unique tag.

External tests
--------------
Sometimes when you are developing a test it's useful to have it packaged
somewhere so your control file can download it, uncompress it and run
it. The convention for packaging test is on
:doc:`External Tests <ExternalTests>`. Make sure you read that session
before you try to package and run your own external tests.

Flow control
------------
One of the benefits of the use of a true programming language for the
control script is the ability to use all of its structural and error
checking features. Here we use a loop to run kernbench with different
threading levels. ::

    for t in [8, 16, 32]:
            job.run_test('kernbench', iterations=2, threads=t, tag='%d' % t)

System information collection
-----------------------------
After every reboot and after every test, Autotest will collect a variety
of standard pieces of system information made up of specific files
grabbed from the filesystem (e.g. ``/proc/meminfo``) and the output of
various commands (e.g.``uname -a``). You can see this output in the
results directories, under ``sysinfo/`` (for per-reboot data) and
``<testname>/sysinfo`` (for pre-test data).

For a full list of what's collected by default you can take a look at
``client/bin/base_sysinfo.py``; however, there also exists a mechanism for
adding extra files and commands to the system info collection inside
your control files. To add a custom file to the log collection you can
call::

    job.add_sysinfo_file("/proc/vmstat")

This would collect the contents of ``/proc/vmstat`` after every reboot. To
collect it on every test you can use the optional ``on_every_test``
parameter, like so::

    job.add_sysinfo_file("/proc/vmstat", on_every_test=True)

There exists a similar method for adding a new command to the sysinfo
collection::

    job.add_sysinfo_command("lspci -v", logfile="lspci.txt")

This will run ``lspci -v`` through the shell on every reboot, logging the
output in *lspci.txt*. The logfile parameter is optional; if you do not
specify it, the logfile will default to the command text with all
whitespace replaced with underscores (e.g. in this case it would use
``lspci_ -v`` as the filename). This method also takes an ``on_every_test``
parameter that can be used to run the collection after every test
instead of every reboot.

Using the profilers facility
----------------------------
You can enable one or more profilers to run during the test. Simply add
them before the tests, and remove them afterwards, e.g.::

    job.profilers.add('oprofile')
    job.run_test('sleeptest')
    job.profilers.delete('oprofile')

If you run multiple tests like this::

    job.profilers.add('oprofile')
    job.run_test('kernbench')
    job.run_test('dbench')
    job.profilers.delete('oprofile')

It will create separate profiling output for each test - generally we do
a separate profiling run inside each test, so as not to perturb the
performance results. Profiling output will appear under
``<testname>/profiling`` in the results directory.

Again, there are examples for all profilers in
``profilers/<profiler-name>/control``.

Creating filesystems
--------------------
We have support built in for creating filesystems. Suppose you wanted to
run the ``fsx`` test against a few different filesystems::

    # Uncomment this line, and replace the device with something sensible
    # for you ...
    # fs = job.filesystem('/dev/hda2', job.tmpdir)

    for fstype in ('ext2', 'ext3'):
            fs.mkfs(fstype)
            fs.mount()
            try:
                    job.run_test('fsx', job.tmpdir, tag=fstype)
            finally:
                    fs.unmount()

or if we want to show off and get really fancy, we could mount EXT3 with
a bunch of different options, and see how the performance compares
across them::

    fs = job.filesystem('/dev/sda3', job.tmpdir)

    iters=10

    for fstype, mountopts, tag in (('ext2', '', 'ext2'),
                                   ('ext3', '-o data=writeback', 'ext3writeback'),
                                   ('ext3', '-o data=ordered', 'ext3ordered'),
                                   ('ext3', '-o data=journal', 'ext3journal')):
            fs.mkfs(fstype)
            fs.mount(args=mountopts)
            try:
                    job.run_test('fsx', job.tmpdir, tag=tag)
                    job.run_test('iozone', job.tmpdir, iterations=iters, tag=tag)
                    job.run_test('dbench', iterations=iters, dir=job.tmpdir, tag=tag)
                    job.run_test('tiobench', dir=job.tmpdir, tag=tag)
            finally:
                    fs.unmount()

Rebooting during a job
----------------------
Where a job needs to cause a system reboot such as when booting a newly
built kernel, there is necessarily an interuption to the control script
execution. The job harness therefore also provides a phased or step
based interaction model. ::

    def step_init():
            job.next_step([step_test])
            testkernel = job.kernel('2.6.18')
            testkernel.config('http://mbligh.org/config/opteron2')
            testkernel.build()
            testkernel.boot()          # does autotest by default

    def step_test():
            job.run_test('kernbench', iterations=2, threads=5)
            job.run_test('dbench', iterations=5)

By defining a ``step_init`` this control script has indicated it is
using step mode. This triggers automatic management of the step state
across breaks in execution (such as a reboot) maintaining forward flow.

It is important to note that the step engine is not meant to work from
the scope of the tests, that is, inside a test module (``job.run_test()``, from
the control file perspective). The reboots and step engine are only meant
to be used from the control file level, since a lot of precautions are
taken when running test code, such as shielding autotest from rogue exceptions
thrown during test code, as well as executing test code on a subprocess, where
it is less likely to break autotest and we can kill that subprocess if it
reaches a timeout.

So this code inside a control file is correct::

    def step_init():
      job.next_step([step_test])
      testkernel = job.kernel('testkernel.rpm')
      testkernel.install()
      testkernel.boot()

    def step_test():
      job.run_test('ltp')


This code, inside a test module, isn't::

    class kerneltest(test.test):
      def execute(self):
        testkernel = job.kernel('testkernel.rpm')
        testkernel.boot()

In broad brush, when using the step engine, the control file is not simply
executed once, but repeatedly executed until it indicates the job is complete.
In a stand-alone context we would expect to re-start execution automatically
on boot when a control file exists, in a managed environment the
managing server would perform the same role.

Obviously looping is more difficult in the face of phase based
execution. The state maintained by the stepping engine is such, that we
can implement a boot based loop using step parameters. ::

    def step_init():
            step_test(1)

    def step_test(iteration):
            if (iteration < 5):
                    job.next_step([step_test, iteration + 1])

            print "boot: %d" % iteration

            job.run_test('kernbench', tag="%d" % i)
            job.reboot()

Running multiple tests in parallel
----------------------------------
The job object also provides a parallel method for running multiple
tasks at the same time. The method takes a variable number of arguments,
each representing a different task to be run in parallel. Each argument
should be a list, where the first item on the list is a function to be
called and all the remaining elements are arguments that will be passed
to the function when it is called. ::

    def first_task():
            job.run_test('kernbench')

    def second_task():
            job.run_test('dbench')

    job.parallel([first_task], [second_task])

This control file will run both *kernbench* and *dbench* at the same time.
Alternatively, this could've been written as::

    job.parallel([job.run_test, 'kernbench'], [job.run_test, 'dbench'])

However, if you want to so something more complex in your tasks than
call a single function then you'll have to define your own functions to
do it, as in the first example.

The parallel jobs are run through fork, so each task will be running in
its own address space and you don't need to worry about performing any
process-local synchronization between your separate tasks. However,
these processes will still be running on the same machine and so still
need to make certain that these tasks don't crash into each other while
accessing shared resources (e.g. the filesystem). This means no
rebooting during parallel tasks, and if you're running the same test in
different tasks, you must be sure to give each task a unique tag
