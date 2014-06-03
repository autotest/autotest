==================================
Autotest job results specification
==================================

On the client machine, results are stored under
`$AUTODIR/results/$JOBNAME/...`, where `$JOBNAME` is `default` unless
you specify otherwise.

Single machine job output format
--------------------------------

The results to each job should conform to:

$AUTODIR/results/default/$JOBNAME/...

-  debug/
-  build<.***tag***>/

   -  src/
   -  build/
   -  patches/
   -  config/
   -  debug/
   -  summary

-  testname<.***tag***>/

   -  results/
   -  profiling/
   -  debug/
   -  tmp/
   -  summary

-  sysinfo/
-  control *(the control script)*
-  summary

Format of status file
---------------------

There are two copies of the status file, one written by the server as we
go called "status.log"), and another copied back from the client (if it
doesn't crash) called "status". Both have the same format specification.
You can read more about the status file format at
:doc:`StatusFileSpecification <../developer/StatusFileSpecification>`.

Multi-machine tests
-------------------

When collating the results together for a multi-machine test, the
results should be formatted with one subdirectory for each machine in
the test, which should contain the job layout above.

There should be a .machines file in the top level that indicates to the
parser that this a multi-machine job, and lists the correct directories
to parse.

There are two ways a multi-machine job can be run:

-  For synchronous jobs, the scheduler kicks off one copy of autoserv,
   with multiple machines passed with "-m" option. In this case, it's
   autoserv's responsibility to create the .machines file. This should
   be appended to, one machine at a time, as the main part of the job is
   kicked off.
-  For asynchronous jobs, the scheduler kicks off one copy of autoserv
   per machine. In this case it is the *scheduler's* responsibility to
   create the .machines fine - we can't do it from autoserv, as we
   didn't know there were multiple machines.

Scheduler behavior
------------------

Results directories and autoserv execution:

-  The scheduler always created a job directory, results/<job tag>
-  For synchronous jobs, the scheduler runs a single instance of
   autoserv with all machines and with the job directory as the results
   directory.
-  For asynchronous single-machine jobs, the scheduler runs a single
   instance of autoserv with that machine and with the job directory as
   the results directory.
-  For asynchronous multi-machine jobs, the scheduler creates a
   results/<job tag>/<hostname> directory for each host and runs one
   instance of autoserv for each host with those directories as results
   directories.

Metahosts always get queue.log.<id> files created in the job directory
(results/<job tag>). These logs contain a single line for each time a
meta-host is assigned a new host or cleared of its host.

Verify information is handled like so:

-  Verify logs from autoserv are always directed to a temporary
   directory using the -r option to autoserv.
-  Verify stdout is also directed to a host log at
   results/hosts/<hostname>.
-  On verify success, the contents of the temporary directory are moved
   to results/<job tag>/<hostname>, UNLESS it was an asynchronous
   single-machine job, in which case the contents are moved to
   results/<job tag>.
-  On verify failure for a non-metahost, the contents are copied as for
   success.
-  On verify failure for a metahost, the contents of the temporary
   directory are deleted. They are never placed in the job directory.
   The only place to find them is in the host log.

The scheduler only creates a .machines file for asynchronous
multi-machine jobs. It creates this file on the fly by appending each
hostname to this file right before running the main autoserv process on
that host.

