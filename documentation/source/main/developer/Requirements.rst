=====================
Autotest requirements
=====================

Make it simple to use

-  Make the system as user-friendly as possible, whilst still allowing
   power users (defaults with overrides!)
-  Provide web front-ends where possible.
-  Capture the "magic" knowledge of how to complex or fiddly operations
   within the harness, not in a person.
-  Low barrier to entry for use and development

Gather as much information as possible

-  Collect stdout and stderr. Break them out per test.
-  Collect dmesg, and serial console where available. Fall back to
   netconsole where not.
-  Gather profiling data from oprofile, vmstat etc.
-  On a hang, gather alt+sysrq+t, etc.
-  Monitor the machine via ssh and ICMP ping for it going down

Allow the developers to DEBUG the test failures

-  Allow them to rerun the exact same test by hand easily.
-  Keep the tests as simple as possible.
-  Provide tracebacks on a failure
-  Provide a flexible control file format that allows developers to do
   custom modifications easily.

Support all types of testing

-  Allow tests to run in parallel
-  Provide reproducible performance benchmarks
-  Allow multiple iterations to be done cleanly for performance testing.
-  Support filesystem tests (mkfs, mount, umount, fsck, etc)
-  Provide test grouping into single units (build, filesystem, etc).
-  Support multi-machine testing and provide syncronization barriers
-  Support virtualized machines (Containers, KVM, Xen)

An OPEN harness

-  Allow us to interact with vendors by sharing tests and problem
   scenarios easily
-  Allow us to interact with the open source community by sharing tests
   and problem scenarios easily
-  Encourage others to contribute to development.
-  Also cleanly support proprietary tests where necessary, and code
   extensions.

Robust operation

-  Allow reinstall of machines from scratch
-  Support power cycle on failure

Scheduling and automation

-  Provide one job queue per machine, or machine group
-  Collect results to a central repository
-  Automatically watch for new software releases, and kick off any job
   based on that.

Provide back-end analysis

-  Suck all the results into a simple, well formatted database.
-  Give a clear PASS/FAIL indication from the client test
-  Allow arbitrary key-value pairs per test iteration
-  Provide clear display of which tests passed on which machines.
-  Graph performance results over time, indicating errors, etc.
-  Compare two releases for statistically significant performance
   differences.
