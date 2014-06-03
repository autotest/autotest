========================================================
Access Control List Management - autotest-rpc-client acl
========================================================

The following actions are available to manage the ACLs:

::

    # autotest-rpc-client acl help
    usage: autotest-rpc-client acl [create|delete|list|add|rm] [options] <acls>

Creating an ACL
---------------

::

    # autotest-rpc-client acl create help
    usage: autotest-rpc-client acl create [options] <acls>

    options:
      -h, --help            show this help message and exit
      -g, --debug           Print debugging information
      --kill-on-failure     Stop at the first failure
      --parse               Print the output using colon separated key=value
                            fields
      -v, --verbose
      -w WEB_SERVER, --web=WEB_SERVER
                            Specify the autotest server to talk to
      -d DESC, --desc=DESC  Creates the ACL with the DESCRIPTION

Only one ACL can be create at a time. You must specify the ACL name and
its description:

::

    # autotest-rpc-client acl create my_acl -d "For testing" -w autotest-dev
    Created ACL:
            my_acl

Deleting an ACL
---------------

::

    # autotest-rpc-client acl delete help
    usage: autotest-rpc-client acl delete [options] <acls>

    options:
      -h, --help            show this help message and exit
      -g, --debug           Print debugging information
      --kill-on-failure     Stop at the first failure
      --parse               Print the output using colon separated key=value
                            fields
      -v, --verbose
      -w WEB_SERVER, --web=WEB_SERVER
                            Specify the autotest server to talk to
      -a ACL_FLIST, --alist=ACL_FLIST
                            File listing the ACLs

You can delete multiple ACLs at a time. They can be specified on the
command line or in a file, using the ``-a|--alist`` option.

::

    autotest-rpc-client acl delete my_acl,my_acl_2
    Deleted ACLs:
            my_acl, my_acl_2

Listing ACLs
------------

::

    # autotest-rpc-client acl list help
    usage: autotest-rpc-client acl list [options] <acls>

    options:
      -h, --help            show this help message and exit
      -g, --debug           Print debugging information
      --kill-on-failure     Stop at the first failure
      --parse               Print the output using colon separated key=value
                            fields
      -v, --verbose
      -w WEB_SERVER, --web=WEB_SERVER
                            Specify the autotest server to talk to
      -a ACL_FLIST, --alist=ACL_FLIST
                            File listing the ACLs
      -u USER, --user=USER  List ACLs containing USER
      -m MACHINE, --machine=MACHINE
                            List ACLs containing MACHINE

You can list all the ACLs, or filter on specific ACLs, users or machines
(exclusively). The ``--verbose`` option provides the list of users and
hosts belonging to the ACLs.

::

    # autotest-rpc-client acl list -w autotest-dev
    Name                     Description
    Everyone
    reserved-qual            Qualification machines
    benchmarking_group       Benchmark machines
    my_acl                   For testing

    # autotest-rpc-client acl list -v -w autotest-dev
    Name                     Description
    Everyone
    Hosts:
            qual0, qual1, qual2, qual3, qual4, host0, host1, host2, host3, host4
            bench0, bench1, bench2, bench3, bench4, test0
    Users:
            user0, user1, user2, user3, user4


    reserved-qual            Qualification machines
    Hosts:
            qual0, qual1, qual2, qual3, qual4
    Users:
            user0


    benchmarking_group       Benchmark machines
    Hosts:
            bench0, bench1, bench2, bench3, bench4
    Users:
            user1, user2

    my_acl                   For testing


    # autotest-rpc-client acl list -w autotest-dev -u user0
    Name                Description
    Everyone
    reserved-qual       Qualification machines


    # autotest-rpc-client acl list -w autotest-dev -m bench0 -v
    Name                   Description
    Everyone
    benchmarking_group     Benchmark machines
    Hosts:
            bench0, bench1, bench2, bench3, bench4
    Users:
            user1, user2

Adding Hosts or Users to an ACL
-------------------------------

::

    # autotest-rpc-client acl add help
    usage: autotest-rpc-client acl add [options] <acls>

    options:
      -h, --help            show this help message and exit
      -g, --debug           Print debugging information
      --kill-on-failure     Stop at the first failure
      --parse               Print the output using colon separated key=value
                            fields
      -v, --verbose
      -w WEB_SERVER, --web=WEB_SERVER
                            Specify the autotest server to talk to
      -a ACL_FLIST, --alist=ACL_FLIST
                            File listing the ACLs
      -u USER, --user=USER  Add USER(s) to the ACL
      --ulist=USER          File containing users to add to the ACL
      -m MACHINE, --machine=MACHINE
                            Add MACHINE(s) to the ACL
      --mlist=MACHINE       File containing machines to add to the ACL

You must specify at least one ACL and one machine or user.

::

    # autotest-rpc-client acl add my_acl -u user0,user1 -v -w autotest-dev
    Added to ACL my_acl user:
            user0, user1

    # cat machine_list
    host0 host1
    host2
    host3,host4

    # autotest-rpc-client acl add my_acl --mlist machine_list -w autotest-dev
    Added to ACL my_acl hosts:
            host0, host1, host2, host3, host4

    # autotest-rpc-client acl list -w autotest-dev -v my*
    Name    Description
    my_acl  For testing
    Hosts:
            host0, host1, host2, host3, host4
    Users:
            user0, user1

Note the usage of wildcard to specify the ACL in the last example:
``my*``

Removing Hosts or Users from an ACL
-----------------------------------

::

    # autotest-rpc-client acl rm help
    usage: autotest-rpc-client acl rm [options] <acls>

    options:
      -h, --help            show this help message and exit
      -g, --debug           Print debugging information
      --kill-on-failure     Stop at the first failure
      --parse               Print the output using colon separated key=value
                            fields
      -v, --verbose
      -w WEB_SERVER, --web=WEB_SERVER
                            Specify the autotest server to talk to
      -a ACL_FLIST, --alist=ACL_FLIST
                            File listing the ACLs
      -u USER, --user=USER  Remove USER(s) from the ACL
      --ulist=USER          File containing users to remove from the ACL
      -m MACHINE, --machine=MACHINE
                            Remove MACHINE(s) from the ACL
      --mlist=MACHINE       File containing machines to remove from the ACL

The options are the same than for adding hosts or users. You must
specify at least one ACL and one machine or user.

::

    # autotest-rpc-client acl rm my_acl -m host3 -w autotest-dev
    Removed from ACL my_acl host:
            host3

    # autotest-rpc-client acl rm my_acl -u user0 -v -w autotest-dev
    Removed from ACL my_acl user:
            user0

    # autotest-rpc-client acl list -w autotest-dev -v my_*
    Name    Description
    my_acl  For testing
    Hosts:
            host0, host1, host2, host4
    Users:
            user1

    # autotest-rpc-client acl delete my_acl -w autotest-dev
    Deleted ACL:
            my_acl

Possible errors and troubleshooting
-----------------------------------

In case of error, add the ``-v`` option to gather more information.

Duplicate ACL:

::

    # autotest-rpc-client acl create my_acl -d "For testing" -w autotest-dev
    Operation add_acl_group failed for: my_acl

    # autotest-rpc-client acl create my_acl -d "For testing" -w autotest-dev -v
    Operation add_acl_group failed for: my_acl
            ValidationError: {'name': 'This value must be unique (my_acl)'}

Adding an unknown user or host:

::

    # autotest-rpc-client acl add my_acl -u foo
    Operation acl_group_add_users failed for: my_acl (foo)

    # autotest-rpc-client acl add my_acl -u foo -v
    Operation acl_group_add_users failed for: my_acl (foo)
            DoesNotExist: User matching query does not exist.

Removing an ACL requires that you are part of this ACL:

::

    # autotest-rpc-client acl delete my_acl -w autotest-dev
    Operation delete_acl_group failed for: my_acl

    # autotest-rpc-client acl delete my_acl -w autotest-dev -v
    Operation delete_acl_group failed for: my_acl
            AclAccessViolation: You do not have access to my_acl

    # Adding yourself to the ACL:
    # autotest-rpc-client acl add -u mylogin my_acl -w autotest-dev
    Added to ACL my_acl user:
            mylogin

    # autotest-rpc-client acl delete my_acl -w autotest-dev
    Deleted ACL:
            my_acl
