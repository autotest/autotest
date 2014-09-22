Diagnosing failures in your results
===================================
This document will describe how to go about triaging your Autotest results and finding out what went wrong.

Basics
------
A lot of times when tests fail there are a number of things that could have come into play. Below are a few
things that should be considered.

- Baseline
- What changed between tests
- Look at the raw results

Having a baseline is an absolute **must**:

- Have you run these tests on this particular system before?
- Did it pass without any issues?

These are questions you should be asking yourself. If you do not have a baseline that is the first thing to establish.
It really is as simple as running a job and making note of the results.

A lot of the time that people have tests fail they do not consider what changed in between tests. Any change what so
ever is important to make note of. From something big like, did I change the kernel? To something small like did I
move my system to a different area which may have impacted the cooling of the system?

Lastly if nothing has changed and you have established a baseline for
your machines it is time to delve into the results.

Looking at raw results
----------------------
There are a few key areas worth looking at when evaluating what could have went wrong with your job. From the 
*View Job* tab click on *raw results log*. Here you will be presented with a directory structure that represents
your job flat files. If you created a job with multiple machines there will be individual directories for each machine.
Navigate to the machine you want to investigate.

The ``debug`` directory
----------------------
All tests run including the main Autotest job will have a ``debug`` directory. Here you will find the majority of the
information you need to diagnose issues with tests.

The following files in ``debug`` directory will give you insight into what Autotest was doing at the time::

    debug/
    ├── build_log.gz
    ├── client.DEBUG
    ├── client.ERROR
    ├── client.INFO
    └── client.WARNING

If you have console support (via ``conmux``) you should also take a look at ``conmux.log``.

If at any point Autotest produced a stacktrace, ``*.ERROR`` will most likely contain this information. That is a
good place to start if the test run failed and you want to see if Autotest itself as at fault for the problem.

If both of these files are clean next we go to the ``<hostname>/test/`` directory.

Example investigation
~~~~~~~~~~~~~~~~~~~~~
This example was created on host without ``time`` utility, I tried to launch *kernbench* (output reduced)::

	# client/autotest-local --verbose run kernbench
	10:01:59 INFO | Writing results to /usr/local/autotest/client/results/default
	...
	10:03:19 DEBUG| Running 'gzip -9 '/usr/local/autotest/client/results/default/kernbench/debug/build_log''
	10:03:19 ERROR| Exception escaping from test:
	Traceback (most recent call last):
	  File "/usr/local/autotest/client/shared/test.py", line 398, in _exec
	    *args, **dargs)
	  File "/usr/local/autotest/client/shared/test.py", line 823, in _call_test_function
	    return func(*args, **dargs)
	  File "/usr/local/autotest/client/shared/test.py", line 738, in _cherry_pick_call
	    return func(*p_args, **p_dargs)
	  File "/usr/local/autotest/client/tests/kernbench/kernbench.py", line 53, in warmup
	    self.kernel.build_timed(self.threads, output=logfile)  # warmup run
	  File "/usr/local/autotest/client/kernel.py", line 377, in build_timed
	    utils.system(build_string)
	  File "/usr/local/autotest/client/shared/utils.py", line 1232, in system
	    verbose=verbose).exit_status
	  File "/usr/local/autotest/client/shared/utils.py", line 918, in run
	    "Command returned non-zero exit status")
	CmdError: Command </usr/bin/time -o /dev/null make  -j 4 vmlinux > /usr/local/autotest/client/results/default/kernbench/debug/build_log 2>&1> failed, rc=127, Command returned non-zero exit status
	* Command:
    	/usr/bin/time -o /dev/null make  -j 4 vmlinux >
    	/usr/local/autotest/client/results/default/kernbench/debug/build_log 2>&1
	Exit status: 127
	Duration: 0.00197100639343

Here we are investigating why *kernbench* failed. The first place we want to look at is the ``debug`` directory.
There we see the following files::

    # tree -s debug/
    debug/
    ├── [         79]  build_log.gz
    ├── [       1345]  client.DEBUG
    ├── [          0]  client.ERROR
    ├── [        511]  client.INFO
    └── [          0]  client.WARNING

As it failed during ``build`` phase I am going to look at ``build_log``::

    $ cat build_log
    /bin/bash: /usr/bin/time: No such file or directory

Well, that is true as::
    
    [user@a5 debug]# which time
    /usr/bin/which: no time in (/usr/local/sbin:/usr/local/bin:/sbin:/bin:/usr/sbin:/usr/bin:/root/bin)
    [user@a5 debug]# ls /usr/bin/time
    ls: cannot access /usr/bin/time: No such file or directory
    
In general test diagnoses should be that straight forward. Obvious this can not cover all cases.

The ``sysinfo`` directory
-------------------------
The ``sysinfo`` directory is exactly what it sounds like. A directory that contains as much information as possible that
can be gathered from the machine::

    # tree sysinfo/
    sysinfo/
    ├── df
    ├── dmesg.gz
    ├── messages.gz
    └── reboot_current -> ../../sysinfo

In general this directory is your second bet for finding issues. Most files are self explanatory, you should always examine
``dmesg`` to make sure your boot was clean. Then depending on what test you were running that failed examine files that
will give you insight to that particular piece of hardware.

Manually running a job on a machine that is causing problems
------------------------------------------------------------
A lot of times you will run into the case that all of your machines but two or three pass. While you may be able to figure
out why most of them failed by looking at files it is sometimes advantageous to run the Autotest process individually on
the problem machines.

Log-in to the machine and change to ``/home/autotest``, there you will find the installation that the server put on this
particular system.

The last control file of the job that was run is also available to you - ``control.autoserv``.

To start the job over again run the following::

    [root@udc autotest]# bin/autotest control.autoserv

This is exactly how the autotest server starts jobs on client machines.

If you have a large control file that runs multiple tests and you are only interested in one or two of them you can safely
edit this file and remove any tests that you know work for sure. A lot of the time failures can be diagnosed by babysitting
a machine and seeing what else is going on with general diagnostic on a machine.
