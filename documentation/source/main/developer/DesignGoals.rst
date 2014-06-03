=====================
Autotest Design Goals
=====================

-  Open source - share tests and problem reproductions
-  Make it simple to write control files, and yet a powerful language
-  Make it simple to write tests and profilers - encourage people to
   contribute

-  Client is standalone, or will plug into any server/scheduler harness

   -  Some people just have single machine, want simple set up.
   -  Corporations each have their own scheduling harness, difficult to
      change
   -  Very little interaction is needed, simple API
   -  Simple handoff from full automated mesh to individual developer

-  Maintainable

   -  Written in one language, that is powerful, and yet easy to
      maintain
   -  Infrastructure that is easily understandable, and allows wide
      variety of people to contribute

-  Modular - the basic infrastructure is cleanly separated with well
   defined APIs.

   -  Easy writing of new tests, profilers, bootloaders, etc
   -  New non-core changes (eg new test) doesn't break other things.
   -  Lower barrier to entry for new developers.
   -  Distributed/scalable maintainership - code controlled by different
      people.

-  Core is small, with few developers

   -  This isn't a super-hard problem.
   -  Most of the intelligence is in sub-modules (eg the tests).

-  Error handling.

   -  Tests that don't produce reliable results are useless in an
      automated world.
   -  Developers don't write error checking easily - need
      'encouragement'.

Modules
-------

-  Core - ties everything together
-  Tests - execute each tests. many, many separate tests modules.

        eg kernbench, aim7, dbench, bonnie, etc.

-  Profilers - gather information on a test whilst it's running, or
   before/after.

        eg readprofile, oprofile, schedstats, gcov, /proc info

-  Results Analysis - Compare equivalent sets of test results. Per test
   / profiler.
-  Kernel build - build kernels, with different patches, configs, etc.

        Will need different variations to cope with mainline, distro
        kernels, etc.

-  Bootloader handling - Install new kernels, and reboot to them, pass
   parameters, etc

        eg. Grub, Lilo, yaboot, zlilo, etc

Key differences
---------------

Here are some of the key changes from previous systems I have seen /
used / written:

-  The job control file is a script. This allows flexibility and power.
-  The client is standalone, so we can easily reproduce problems without
   the server.
-  Code and tests are modular - you can allow loser control over tests
   than the core.
-  Code is GPL.

