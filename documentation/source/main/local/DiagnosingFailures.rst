===================================
Diagnosing Failures in Your Results
===================================

This document will describe how to go about triaging your Autotest
results and finding out what went wrong.

Basics
------

A lot of times when tests fail there are a number of things that could
have come into play. Below are a few things that should be considered.

-  Baseline
-  What changed between tests
-  Look at the raw results

Having a baseline is an absolute must. Have you run these tests on this
particular system before? Did it pass without any issues? These are
questions you should be asking yourself. If you do not have a baseline
that is the first thing to establish. It really is as simple as running
a job and making note of the results.

A lot of the time that people have tests fail they do not consider what
changed in between tests. Any change what so ever is important to make
note of. From something big like, did I change the kernel? To something
small like did I move my system to a different area which may have
impacted the cooling of the system?

Lastly if nothing has changed and you have established a baseline for
your machines it is time to delve into the results.

Looking at Raw Results
----------------------

There are a few key areas worth looking at when evaluating what could
have went wrong with your job. From the*View Job*tab click on *raw
results log.*Here you will be presented with a directory structure that
represents your job flat files. If you created a job with multiple
machines there will be individual directories for each machine. Navigate
to the machine you want to investigate.

The debug Directory
-------------------

All tests run including the main autotest job will have a debug
directory. Here you will find the majority of the information you need
to diagnose issues with tests.

The following files will give you insight into what autotest was doing
at the time.

-  debug/autoserv.ERROR
-  debug/autoserv.DEBUG
-  debug/client.log.\*

If you have console support (via conmux) you should also take a look at
conmux.log

If at any point autotest produced a stacktrace, autoserv.ERROR will most
likely contain this information. That is a good place to start if the
test run failed and you want to see if autotest itself as at fault for
the problem.

If both of these files are clean next we go to the <hostname>/test/
directory.

For example (example no longer exists):

`http://test.kernel.org/results/IBM/126959/kernbench/ <http://test.kernel.org/results/IBM/126959/kernbench/>`_

Here we are investigating why kernbench failed for this particular
kernel. The first place we want to look at is the *debug* directory.
There we see three files

-  build\_log
-  stderr
-  stdout

Starting with stderr we see

::

    /usr/local/autobench/autotest/tests/kernbench/src/linux/arch/x86_64/defconfig:111: trying to assign nonexistent symbol HAVE_DEC_LOCK

Alright that gives us some insight. Lets poke around a bit more. The
stdout file is 45k I am going to skip that and look at build\_log:

::

      SYMLINK include/asm -> include/asm-x86_64
      CHK     include/linux/version.h
      HOSTCC  scripts/basic/fixdep
      UPD     include/linux/version.h
      HOSTCC  scripts/basic/split-include
      HOSTCC  scripts/basic/docproc
      SPLIT   include/linux/autoconf.h -> include/config/*
      CC      arch/x86_64/kernel/asm-offsets.s
    arch/x86_64/kernel/asm-offsets.c:1: error: code model `kernel' not supported in the 32 bit mode
      HOSTCC  scripts/kallsyms
      HOSTCC  scripts/conmakehash
      HOSTCC  scripts/bin2c
    make[1]: *** [arch/x86_64/kernel/asm-offsets.s] Error 1
    make: *** [prepare0] Error 2
    make: *** Waiting for unfinished jobs....
      CC      scripts/mod/empty.o
    scripts/mod/empty.c:1: error: code model `kernel' not supported in the 32 bit mode
      HOSTCC  scripts/mod/mk_elfconfig
    make[2]: *** [scripts/mod/empty.o] Error 1
    make[2]: *** Waiting for unfinished jobs....
    make[1]: *** [scripts/mod] Error 2
    make[1]: *** Waiting for unfinished jobs....
    make: *** [scripts] Error 2

The two errors listed there are common errors when trying to cross
compile a 64 bit kernel on a 32 bit system.

In general test diagnoses should be that straight forward. Obvious this
cannot cover all cases.

The sysinfo Directory
---------------------

The sysinfo directory is exactly what it sounds like. A directory that
contains as much information as possible that can be gathered from the
machine. Of all the information these are files you should pay
particular information to:

-  dmesg
-  uname -a
-  cmdline

   -  The kernel boot command line

-  df
-  meminfo

In general this directory is your second bet for finding issues. Most
files are self explanatory, you should always examine dmesg to make sure
your boot was clean. Then depending on what test you were running that
failed examine files that will give you insight to that particular piece
of hardware.

Manually running a job on a machine that is causing problems
------------------------------------------------------------

A lot of times you will run into the case that all of your machines but
two or three pass. While you may be able to figure out why most of them
failed by looking at files it is sometimes advantageous to run the
autotest process individually on the problem machines

Log in to the machine and change to */home/autotest*, there you will
find the installation that the server put on this particular system.

The last control file of the job that was run is also available to you:
**control.autoserv**

To start the job over again run the following:

::

    [root@udc autotest]#bin/autotest control.autoserv

This is exactly how the autotest server starts jobs on client machines.

If you have a large control file that runs multiple tests and you are
only interested in one or two of them you can safely edit this file and
remove any tests that you know work for sure. A lot of the time failures
can be diagnosed by babysitting a machine and seeing what else is going
on with general diagnostic on a machine.

