Keyval files in Autotest
========================
There are several "keyval" files in the ``results`` directory. These take the simple form ::

    key1=value1
    key2=value2

Below we describe what information is in which file.

Job level keyval
----------------
This file contains high level information about the job such as when it was queued, started, finished, the username
of the submitter, and what machines are involved.

Synchronous multi-machine jobs
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
When running a multi-machine job synchronously, you will end up with multiple "job level" keyval files; at the very
least, one upper-level keyval file in the root results directory, and one in each machine subdirectory. In the results
database each machine will be interpreted as a separate set of results, with the total job keyval data being
composed of data from the "uppermost" of the keyval files (i.e. the single job level keyval in the root dir). The single
exception to this is the ``hostname`` field - this is taken from the machine directory.

Test level keyval
-----------------
This file contains the version of the test, and some per-test system information (parsed from the ``sysinfo`` dir) so that
we can load it up into the database easily.

Results level keyval
--------------------
This file contains performance information for a test. Maybe something like ::

    throughput=100
    latency=12

If we ran multiple iterations of a test, there will be repeteaed keyvals in there, separated by a blank line::

    throughput=101
    latency=12.9

    throughput=100
    latency=11.2

    throughput=96
    latency=13.1
