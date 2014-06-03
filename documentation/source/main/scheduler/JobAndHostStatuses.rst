=====================
Job and Host Statuses
=====================

Job Statuses
------------

-  **Queued** -- the job is waiting for machines to become ready and/or
   accessible, or the scheduler has simply not picked up the job yet. A
   job can go back to this state from Verifying when a machine fails
   verify and goes to repair.
-  **Verifying** -- the job is going through pre-job cleanup and/or
   verification. See host statuses **Cleaning** and **Verifying**. This
   is controlled by the job options *reboot before* and *skip verify*
   and well as by :doc:`Host Protections <../frontend/Web/HostProtections>`
   (namely *Do not verify*).
-  **Pending** -- the job is ready to run on this host but is waiting
   for other hosts because it's a synchronous job.
-  **Starting** -- the job is about to start. Jobs should only stay in
   this state when the system is at its capacity limit.
-  **Running** -- the job is running (Autoserv is actively running on
   the server).
-  **Gathering** -- after Autoserv is aborted (or otherwise unexpectedly
   killed), a job will enter this state to gather uncollected logs and
   crash information from the machine under test. This stage will also
   wait several hours for the machine to come back if it went down.
-  **Parsing** -- the parser is running a final reparse of job results.
   This stage should be very brief unless the system is under heavy
   load, in which case parses are throttled by the results database.
-  **Completed** -- the job is over and Autoserv completed successfully
   (note that *functional tests* may have failed, but the *job* ran all
   tests without error).
-  **Failed** -- the job is over and Autoserv exited with some failure.
-  **Aborted** -- the job is over and was aborted.

Host Statuses
-------------

-  **Ready** -- the host is idle and ready to run.
-  **Cleaning** -- the host is running pre-job, post-job, or post-abort
   cleanup (see job options *reboot before* and *reboot after*). The
   cleanup phase includes rebooting the host and, optionally,
   site-specific cleanup tasks.
-  **Verifying** -- the host is running pre-job or post-abort verify
   (see job option *skip verify*). The verify phase checks for basic
   connectivity, disk space requirements, and, optionally, site-specific
   conditions.
-  **Repairing** -- the host is undergoing attempted repair; this
   includes rebooting, waiting for the host to come up, clearing off
   disks, and, optionally, site-specific extensions. This is controlled
   by :doc:`Host Protections <../frontend/Web/HostProtections>`.
-  **Pending** -- see the job state **Pending**.
-  **Running** -- the host is being held for a running job. This
   includes time that Autoserv is actually running (job state
   **Running**) as well as the job **Gathering** phase.
-  **Repair Failed** -- the host failed repair and it currently assumed
   to be in an unusable state. Scheduling a new job against this host
   will reset it to the **Ready** state.

See also
--------

-  The flowchart at
   :doc:`SchedulerSpecification <SchedulerSpecification>` illustrates
   how hosts and jobs move through these states.
-  :doc:`Web Frontend Howto <../frontend/Web/WebFrontendHowTo>`
   documents the above-mentioned job options.

