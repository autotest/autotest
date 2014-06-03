======================================
Understanding the TKO Results Database
======================================

This page will (hopefully) help you understand how results are
structured in the Autotest results database, and how you can best
structure results for your test.

Structure of test results
-------------------------

The core results entity produced when you run a tests is a **Test
Result**. (The DB model name is simply "Test", but "Test Result" is more
clear, so I'm going to use that term here.) Each Test Result has a
number of fields, most importantly the name of that test that ran and
the status of the test outcome. Test Results also include timestamps and
links to a few related objects, including the kernel and machine on
which the test ran, and the job that ran the test. Each of these objects
includes other fields - see :doc:`TKO database <TkoDatabase>` for the full list.

Each Test Result can also have any number of **Test Attributes**, each
of which is a key-value pair of strings. Note that some Test Attributes
are included with each test automatically, including information on test
parameters and machine sysinfo.

Furthermore, each Test Result can have any number of **Iterations**,
indexed from zero. These are primarily for use by performance tests.

-  Each Iteration can have any number of **Iteration Attributes**, each
   of which is a key-value pair of strings.
-  Each Iteration can also have any number of **Iteration Results**,
   each of which is a key-value pair with floating-point values (and
   string keys, as usual). This is the only way to record numerical data
   for a test. It is used for all performance tests.

Note that, despite the names, both of these kinds of iteration keyvals
are intended to describe results-oriented information. The only
difference is that one holds string-valued results while the other holds
numerical results. Neither type of iteration keyval is intended to hold
information about how the test ran (such as test parameters). By design,
all iterations within a test should run the exact same way. The only
intended purpose of iterations is to gather more samples for statistical
purposes. If you want to run a test multiple times varying parameters,
you should create multiple Test Results (see below).

To summarize:

-  Job

   -  Test Results

      -  Test Attributes (string key -> string value)
      -  Iterations (indexed from 0)

         -  Iteration Attributes (string key -> string value)
         -  Iteration Results (string key -> float value)

How are test results created?
-----------------------------

Each call to ``job.run_test()`` implicitly creates one Test Result. The
status of the Test Result is determined by what, if any, exception was
raised (and escaped) during test execution. Any calls to record keyvals
within the test will be associated with the Test Result for that call to
``run_test()``.

If you want to create many Test Result objects, you must have code to
call ``job.run_test()`` many times. This code must reside in the control
file, or in a library called by the control file, but not within the
test class itself (since everything in the test class executes within a
call to ``run_test()``).

A new issue arises when running the same test multiple times within a
job. This will generate many Test Results with the same test name, but
there must be a unique identifier for each Test Result (other than the
database ID). This brings another Test Result field into play --
``subdir``, the subdirectory containing the result files for that Test
Result. ``subdir`` is normally equal to the test name, but this field
must be unique among all Test Results for a job. When running a test
multiple times, unique ``subdir``s are usually achieved by passing a
unique ``tag`` with each call to ``job.run_test()`` for a particular
test. The ``subdir`` then becomes ``$test_name.$tag``.

Further reading
---------------

-  :doc:`AutotestApi <../developer/Tests/APIOverview>`
   explains how each of these keyvals can be recorded by test code using
   Test APIs.
-  :doc:`TkoDatabase <TkoDatabase>` illustrates the database schema.
   Note that it does not map directly onto these concepts. In
   particular, there's no table for iterations themselves, only the
   iteration keyvals. The existence of iterations themselves is
   implicit.
-  `Keyval <../local/Keyval>` explains the placement and format of keyval
   files within the results directories. These are written by Autoserv
   and read by the Parser to fill in the database.

