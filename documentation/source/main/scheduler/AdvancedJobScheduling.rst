Advanced Job Scheduling
=======================

This page documents some of the more advanced things that the scheduler
is capable of.

Metahost entries ("Run on any...")
----------------------------------

Jobs can be scheduled to run against any host with a particular label.
This is used through the frontend with the "Run on any..." box (for
example, "run on any x86"). Such entries are called *metahost* entries.
Metahost entries will be assigned to eligible and ready hosts
dynamically by the scheduler.

"Only if needed" labels
-----------------------

If a label is marked *only if needed*, any host with that label is not
eligible for assignment to metahost entries unless

-  the job's *dependency labels* includes that label, or
-  the metahost is against that particular label.

Note that such hosts can still be used by any job if selected explicitly
(i.e. not through a metahost).

Atomic Groups
-------------

An *atomic group* is a group of machines that must be scheduled together
for a job. Regular jobs cannot be scheduled against hosts within these
groups; they must be used together.

Atomic groups are created in the admin interface to specify classes of
atomic groups of machines (for example, "x86-64 rack" might be an atomic
group). Labels can then be marked as instances of a particular atomic
group; in this case, a label would include all machines for a particular
group (for instance, "x86-64 rack `#1 <../ticket/1>`_"). Finally,
machines can be added to these labels to form the actual groups.

Example
~~~~~~~

As an example, assume you have twenty hosts, ten x86-64 and ten i386.
You wish to run a test that requires a rack of five machines. You might
do the following:

-  Create two atomic groups, "x86-64 rack" and "i386 rack".
-  Create four labels: "x86-64 rack #1" and "x86-64 rack #2" are both
   labels with atomic group type "x86-64 rack", and likewise for i386.
-  Assign five x86-64 hosts to the "x86-64 rack #1" label, and the
   remaining five to the "x86-64 rack #2" label. Likewise for i386.

Now, you could run a job with synch count = 5, and specify that you want
to run against one atomic group of type "x86-64 rack" and one of type
"i386 rack". The scheduler will dynamically pick a rack of each type
that is ready to run the job. Users trying to schedule regular jobs
against hosts within these groups will be unable to do so; they will
remain reserved for jobs intended for the entire group.

Variable host counts
~~~~~~~~~~~~~~~~~~~~

Some tests can run against a variable number of machines, and you may
with to run such a test against all the ready machines within an atomic
group, within some bounds. The scheduler can do this for you -- at job
run time, it will verify all machines in the group and use all the ones
that are ready. The following constraints are available:

-  The "max number of machines" attribute on the Atomic Group specifies
   the maximum number of machines to use at once.
-  The job's "synch count" attribute specifies the minimum number of
   machines to use from the group. If fewer than this number are ready,
   the job will be unable to run. Note that this behavior is unique to
   jobs run against atomic groups -- normally, synch count specifies the
   exact number of machines to use, but with an atomic group, the
   scheduler will use as many machines as are ready (up to the maximum).

