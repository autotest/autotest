===============================
Autotest Command Line Interface
===============================

Autotest provides a set of commands that can be used to manage the
autotest database, as well as schedule and manage jobs.

The commands are in the ``./cli`` directory.

The main command is called 'autotest-rpc-client'. The general syntax is:

::

    autotest-rpc-client <topic> <action> <items> [options]

Where:

-  topic is one of: acl, host, job, label or user
-  action is one of: create, delete, list, stat, mod, add, rm. Not all
   the actions are available for all topics.

Topic References
----------------

The references for the different topics are available for acl?, label?,
host?, user?, test? and job? management

Common options
--------------

The options common to all commands are:

-  ``help``: displays the options specific to the topic and/or action.
   It can be used as:

   -  autotest-rpc-client help
   -  autotest-rpc-client <topic> help
   -  autotest-rpc-client <topic> <action> help

-  ``-w|--web``: specifies the autotest server to use (see below).
-  ``--parse``: formats the output in colon separated key=values pairs.
-  ``--kill-on-failure``: stops processing the arguments at the first
   failure. Default is to continue and displays the failures at the end.
-  ``-v|--verbose``: Displays more information.

Server Access
-------------

By default, the commands access the server at: ``http://autotest``. This
can be overwritten by setting the ``AUTOTEST_WEB`` environment variable
or using the ``-w|--web`` option using only the hostname. The order of
priority is:

#. the command line option,
#. the AUTOTEST\_WEB environment variable
#. the default 'autotest' server.

Wildcard
--------

The ``list`` action accepts the \* wildcard at the end of a filter to
match all items starting with a pattern. It may be necessary to escape
it to avoid the \* to be interpreted by the shell.

::

    # autotest-rpc-client host list host1\*
    Host      Status  Locked  Platform  Labels
    host1     Ready   False
    host12    Ready   False
    host13    Ready   False
    host14    Ready   False
    host15    Ready   False

File List Format
----------------

Several options can take a file as an argument. The file can contain
space- **or** comma-separated list of items e.g.,

::

    # cat file_list
    host0
    host1
    host2,host3
    host4 host5

Note the ``host1, host2`` (comma **and** space) is not a valid syntax
