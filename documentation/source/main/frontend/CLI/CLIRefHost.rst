==========================================
Host Management - autotest-rpc-client host
==========================================

**NOTE: THIS IS ONLY PARTIALLY DONE.**

The following actions are available to manage hosts:

::

    # autotest-rpc-client host help
    Usage: autotest-rpc-client host [create|delete|list|stat|mod|jobs] [options] <hosts>

    Options:
      -h, --help            show this help message and exit
      -g, --debug           Print debugging information
      --kill-on-failure     Stop at the first failure
      --parse               Print the output using colon separated key=value
                            fields
      -v, --verbose
      -w WEB_SERVER, --web=WEB_SERVER
                            Specify the autotest server to talk to
      -M MACHINE_FLIST, --mlist=MACHINE_FLIST
                            File listing the machines

Creating a Host
---------------

::

    #  autotest-rpc-client host create help
    usage: autotest-rpc-client host create [options] <hosts>

    options:
      -h, --help            show this help message and exit
      -g, --debug           Print debugging information
      --kill-on-failure     Stop at the first failure
      --parse               Print the output using colon separated key=value
                            fields
      -v, --verbose
      -w WEB_SERVER, --web=WEB_SERVER
                            Specify the autotest server to talk to
      --mlist=MACHINE_FLIST
                            File listing the machines
      -l, --lock            Create the hosts as locked
      -u, --unlock          Create the hosts as unlocked (default)
      -t PLATFORM, --platform=PLATFORM
                            Sets the platform label
      -b LABELS, --labels=LABELS
                            Comma separated list of labels
      --blist=LABEL_FLIST   File listing the labels
      -a ACLS, --acls=ACLS  Comma separated list of ACLs
      --alist=ACL_FLIST     File listing the acls

Multiple hosts can be created with one command. The hostname(s) can be
specified on the command line or in a file using the ``--mlist`` option.

You can specify the platform type, labels and ACLs for all the newly
added hosts. If you want the hosts to be locked, specify ``--locked``
flag. The scheduler will not assign jobs to a locked host.

::

    # cat /tmp/my_machines
    host0
    host1

    # Create 2 hosts, locked and add them to the my_acl ACL.
    # autotest-rpc-client host create --mlist /tmp/my_machines -a my_acl -l
    Added hosts:
            host0, host1

Deleting a Host
---------------

::

    # autotest-rpc-client host delete help
    usage: autotest-rpc-client host delete [options] <hosts>

    options:
      -h, --help            show this help message and exit
      -g, --debug           Print debugging information
      --kill-on-failure     Stop at the first failure
      --parse               Print the output using colon separated key=value
                            fields
      -v, --verbose
      -w WEB_SERVER, --web=WEB_SERVER
                            Specify the autotest server to talk to
      --mlist=MACHINE_FLIST
                            File listing the machines

Multiple hosts can be deleted with one CLI. The hostname(s) can be
specified on the command line or in a file using the ``--mlist`` option.

::

    # The list can be comma or space separated.
    # autotest-rpc-client host delete host1,host0 host2
    Deleted hosts:
            host0, host1, host2

Listing Hosts
-------------

::

    # autotest-rpc-client host list help
    Usage: autotest-rpc-client host list [options] <hosts>

    Options:
      -h, --help            show this help message and exit
      -g, --debug           Print debugging information
      --kill-on-failure     Stop at the first failure
      --parse               Print the output using colon separated key=value
                            fields
      -v, --verbose
      -w WEB_SERVER, --web=WEB_SERVER
                            Specify the autotest server to talk to
      -M MACHINE_FLIST, --mlist=MACHINE_FLIST
                            File listing the machines
      -b LABEL, --label=LABEL
                            Only list hosts with this label
      -s STATUS, --status=STATUS
                            Only list hosts with this status
      -a ACL, --acl=ACL     Only list hosts within this ACL
      -u USER, --user=USER  Only list hosts available to this user

You can which host(s) you want to display using a combination of options
and wildcards.

::

    # List all the hosts
    # autotest-rpc-client host list
    Host   Status  Locked  Platform  Labels
    host1  Ready   True              label1
    host0  Ready   True              label0
    mach0  Ready   True
    mach1  Ready   True

    # Only hosts starting with ho
    # autotest-rpc-client host list  ho\*
    Host   Status  Locked  Platform  Labels
    host1  Ready   True              label1
    host0  Ready   True              label0

    # Only hosts having the label0 label
    # autotest-rpc-client host list -b label0
    Host   Status  Locked  Platform  Labels
    host0  Ready   True              label0

    # Only hosts having a label starting with lab
    # autotest-rpc-client host list -b lab\*
    Host   Status  Locked  Platform  Labels
    host1  Ready   True              label1
    host0  Ready   True              label0

    # Only hosts starting with ho and having a label starting with la
    # autotest-rpc-client host list -b la\* ho\*
    Host   Status  Locked  Platform  Labels
    host1  Ready   True              label1
    host0  Ready   True              label0

Getting Hosts Status
--------------------

::

    # autotest-rpc-client host stat help
    Usage: autotest-rpc-client host stat [options] <hosts>

    Options:
      -h, --help            show this help message and exit
      -g, --debug           Print debugging information
      --kill-on-failure     Stop at the first failure
      --parse               Print the output using colon separated key=value
                            fields
      -v, --verbose
      -w WEB_SERVER, --web=WEB_SERVER
                            Specify the autotest server to talk to
      -M MACHINE_FLIST, --mlist=MACHINE_FLIST

To display host information:

::

    # autotest-rpc-client host stat host0
    -----
    Host: host0
    Platform: x386
    Status: Repair Failed
    Locked: False
    Locked by: None
    Locked time: None
    Protection: Repair filesystem only

    ACLs:
    Id   Name
    110  acl0
    136  acl1

    Labels:
    Id   Name
    392  standard_config
    428  my_machines

Modifying Hosts Status
----------------------

::

    # autotest-rpc-client host mod help
    Usage: autotest-rpc-client host mod [options] <hosts>

    Options:
      -h, --help            show this help message and exit
      -g, --debug           Print debugging information
      --kill-on-failure     Stop at the first failure
      --parse               Print the output using colon separated key=value
                            fields
      -v, --verbose
      -w WEB_SERVER, --web=WEB_SERVER
                            Specify the autotest server to talk to
      -M MACHINE_FLIST, --mlist=MACHINE_FLIST
                            File listing the machines
      -y, --ready           Mark this host ready
      -d, --dead            Mark this host dead
      -l, --lock            Lock hosts
      -u, --unlock          Unlock hosts
      -p PROTECTION, --protection=PROTECTION
                            Set the protection level on a host.  Must be one of:
                            "Repair filesystem only", "No protection", or "Do not
                            repair"

You can change the various states of the machines:

::

    # Lock all ho* hosts:
    # autotest-rpc-client host mod -l ho*
    Locked hosts:
            host0, host1

    # Hosts have been repaired, put them back in the pool:
    # autotest-rpc-client host mod --ready host0
    Set status to Ready for host:
            host0

