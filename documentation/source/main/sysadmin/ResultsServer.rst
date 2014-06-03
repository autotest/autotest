=============================================
Setting up an Autotest Drone (Results Server)
=============================================

After completing this document you should have at the very minimum two
servers setup. The Autotest system you had setup initially and another
system for storing the results of job runs. This document assumes that
you have a working Autotest server as described in: `Autotest Server
Install <AutotestServerInstall>`_.

Benefits of setting up a results server

-  Offload all jobs to one central location that is only used for
   storing the results.
-  Offload the main autotest server from having to also store results
   copied back to it.
-  Off site copy of results.

The benefits of setting up a results server are most apparent when you
have Autotest running jobs on multiple drones.

Global Configuration Variables
------------------------------

In the `global\_config.ini <GlobalConfig>`_ SCHEDULER section there
are some variables you can use to tell Autotest where to archive
results:

::

    [SCHEDULER]
    results_host: localhost
    results_host_installation_directory:

-  *results\_host* defines the host where results should be offloaded.
   This is typically localhost and basically tells Autotest not to copy
   files anywhere else after a job completes.
-  *results\_host\_installation\_directory* is used to specify a custom
   directory if it is required. By default it uses whatever the Autotest
   server uses on the scheduler commandline. Most people will want to
   leave this at default.

Our drone system in general allows for more flexibility using "special
variables" that do not exist in the default global\_config.ini but can
be used to change the behavior of the system. Below will be an example
of using the **HOSTNAME\_username** directive to make all results
collection be done as a user I specify.

Updated [SCHEDULER] configuration
---------------------------------

::

    [SCHEDULER]
     max_processes_per_drone: 1000
     max_jobs_started_per_cycle: 100
     max_parse_processes: 5
     max_transfer_processes: 50
     drones: localhost
     drone_installation_directory: /usr/local/autotest
     results_host: dumpster
     results_host_installation_directory:
     dumpster_username: offloader**
     secs_to_wait_for_atomic_group_hosts: 600
     reverify_period_minutes: 0


With the above settings, all jobs from all drones (including a regular
localhost drone) will be copied to hostname *dumpster* using username
*offloader*. The username setting is using the aforementioned special
variable. If I did not use *dumpster_username* the results server would
have data copied to it as the user the autoserv process is run under
(Which in most cases would be autotest).

* Make sure you keep the global\_config.ini files in sync
throughout your whole Autotest system otherwise you may experience very
strange issues.

Software Required on the Results Server
---------------------------------------

A results server requires all the same software a Drone requires or a
local Autotest server without MySQL. You will need a full Autotest
installation on the system. If you are not doing anything special to
synchronize all of your Autotest Server Systems then you can simply
rsync your current server Autotest directory to your Results server.

Example Rsync command:

**rsync -av /usr/local/autotest dudicus:/usr/local/autotest**

How the two installations are kept in sync is the job of the system
administrator we do not attempt to solve this problem.

Start/Restart the Scheduler
---------------------------

Once you have the following steps complete restart the scheduler and you
will be running with a results server

-  Your global configuration has been updated
-  You've installed all required software on the results server
-  An updated global\_config.ini as described above is on all of your
   Autotest System Servers.

Restart your scheduler and run a few jobs to make sure files are showing
up.

Results will show up in your autotest directory under results. For
example */usr/local/autotest/results/*

Tips and Tricks
---------------

-  Often times corporate accounts are weighed down with other
   authentication methods like LDAP that can make transfers very slow.
   Try setting up a local account that uses your autotest users ssh key.
-  SSH connections are dropped when a large job completes: Modify the
   following variable in your `/etc/sshd\_config`: **MaxStartUps XXXX**.
   This will allow half complete connections to wait around until your
   system is available to process all of the connections.


