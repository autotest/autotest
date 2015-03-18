========================================
Configuring hosts on the Autotest server
========================================

How to configure your hosts in the Autotest service.

Hosts
-----

Hosts must be added to the Autotest system before they can be used to
run tests. Hosts can be added through the *one-time hosts* interface,
but for repeated tests it's better to add them to the system properly.
Hosts can be added through the admin interface
(`WebFrontendHowTo <WebFrontendHowTo>`_) or the CLI
(`CLIHowTo <cliRefHost>`_). Host options include:

-  **hostname** -- this is how the host will be identified in the
   frontend and CLI and how Autotest will attempt to connect to the
   host.
-  **locked** -- when a host is locked, no jobs will be scheduled on the
   host. Existing jobs will continue to completion.
-  **protection** -- see `HostProtections <HostProtections>`_.

Labels
------

Labels can be applied to machines to indicates arbitrary features of
machines. The most common usage of labels is to indicate a machine's
platform, but they can also be used to indicate machine capabilities or
anything else the user likes. Labels are displayed in the frontend but
also play an important role in
`AdvancedJobScheduling <AdvancedJobScheduling>`_.

-  **name** -- this is how the label will be identified in the frontend
   and CLI
-  **kernel\_config** -- **deprecated** this field is generally unused
   and should be removed
-  **platform** -- true if this label indicates a platform type. This
   option affects web frontend display only and has no effect on
   scheduling.
-  **only\_if\_needed** -- see
   `AdvancedJobScheduling#Onlyifneededlabels <AdvancedJobScheduling#Onlyifneededlabels>`_.

ACLs
----

Access Control Lists restrict which users can perform certain actions on
machines. They are primarily used to prevent other users from running
jobs on a particular user's machines. See
`ACLBehavior <ACLBehavior>`_ for details on what ACLs control and
how they work.

Each ACL is associated with some group of users and some group of
machines. A user has ACL access to a machine if she is in any ACL group
with that machine. By default, all users and and machines are in the
"Everyone" ACL, which essentially makes a machine publicly shared in the
system.

Any user can create a new ACL using web frontend
(`WebFrontendHowTo <WebFrontendHowTo>`_) or CLI
(`CLIHowTo <cliRefACL>`_).

Atomic Groups
-------------

See
`AdvancedJobScheduling#AtomicGroups <AdvancedJobScheduling#AtomicGroups>`_

