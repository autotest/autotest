========================================================
Setting up a distributed Autotest production environment
========================================================

This document aims to discuss how to setup a distributed autotest
environment.

The problem
-----------

The standard Autotest production environment uses a single server to do
many things:

- Run MySQL for the frontend and results databases
- Run Apache for the AFE and TKO web interfaces
- Run a scheduler to coordinate job executions
- Run many Autoserv processes to execute tests on remote machines
- Store all results in a single results repository directory

As the size of an Autotest server grows, and in particular as the number
of concurrent machines under test grows, this single-server setup can
run into scalability limitations quickly. In order to allow continued
growth of an Autotest production environment, the Autotest system
supports breaking out these roles onto different machines. Once properly
configured, the difference should be nearly invisible to users.

MySQL and Apache
----------------

Autotest has always been capable of using a remote database server -the
global\_config.ini file contains parameters for database hostname. The
web interfaces are almost exclusively dependent on the database, so they
too are fairly simple to break out.

Scheduler, Autoserv and the Results Repository
----------------------------------------------

The main complexity in a distributed setup arises in the scheduler. The
scheduler is responsible for reading the database, executing Autoserv
processes, and gathering the results into a central location. So the
scheduler must be capable of executing Autoserv processes on remote
machines and transferring the results files to a separate results
repository machine. This behavior is achieved through the following
global\_config parameters:

- `` drones ``: a "drone" is a machine that will be used to execute
   Autoserv processes. This parameter should be a comma-separated list
   of hostnames for machines to be used as drones.
- `` results_host ``: the hostname of the machine to use as the results
   repository.

Any machine used as a drone or results repository must be set up for
passwordless SSH from the scheduler, just as for machines under test. In
addition, these hosts must have the results directory created with
read/write permissions for the SSH user (the results directory is passed
to the scheduler on the command line). They must also have Autotest
installed at the location given in the
`` drone_installation_directory `` global\_config option. This may be
the same as the results directory. Finally, since the parser will run on
the drones, they must have TKO database parameters properly configured
in global\_config.ini.

Note that `` localhost `` is a valid hostname for either option, and
when using localhost, SSH is not required to be set up. For a
single-server setup, both options would simply be set to
`` localhost ``.

See `GlobalConfig <GlobalConfig>`_ for more options that can be
used.

Viewing results files from the web
----------------------------------

With the above setup, your jobs will execute successfully, but viewing
results through the web remains a challenge because the logs may not
reside on the same machine as Apache. For this reason, both AFE and TKO
perform all log retrieval through the `` tko/retrieve_logs.cgi ``
script. This script reads the global\_config options above, as well as a
third:

- `` archive_host `` (optional): an additional hostname to check for
   results files when they cannot be found elsewhere. System
   administrators may manually move results off of the main results
   repository to this machine.

`` retrieve_logs.cgi `` attempts to fetch the requested log file from
the results repository, then from each drone, and finally from the
archive host, until it succeeds. If it succeeds, it redirects the user
to the appropriate host. For this to work properly, all drones, the
results repository host, and the optional archive host must **all** be
running Apache with the results directory mapped to `` /results ``.

Recommendations
---------------

So now you know how to configure a distributed Autotest environment. But
how do you figure out what distribution of components is necessary? Here
are a few general tips:

-  The most important thing to do is to run the Autoserv processes on a
   different machine than MySQL. These components are usually the two
   biggest resource hogs. Each Autoserv process should not be too
   resource-intensive, but since there will be at least one process per
   host under test, there can be a huge number of Autoserv processes
   running concurrently.
-  Since the web interfaces and the scheduler depend heavily on the
   database, it can be beneficial to run Apache and the Scheduler on the
   same machine as MySQL. Since Apache and the Scheduler are not very
   resource intensive, this is generally not a performance problem.
-  The drones will often end up being the bottleneck in a large system,
   and the Autoserv processes will most likely be IO-bound. Therefore,
   configuring drones with performance-enhancing RAID setups can provide
   a dramatic increase in system capacity.
-  For system reliability, it is often beneficial to isolate drones for
   running Autoserv processes only. Large numbers of Autoserv processes
   are the most likely components to crash the system. With dedicated
   drones, an machine crash due to Autoserv will not affect the web
   interfaces, and if multiple drones are being used, jobs can continue
   to run uninterrupted on other drones.

