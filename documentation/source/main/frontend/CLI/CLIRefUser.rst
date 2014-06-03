==========================================
User Management - autotest-rpc-client user
==========================================

The following actions are available to manage users:

::

    # autotest-rpc-client user help
    usage: autotest-rpc-client user list [options] <users>

    options:
      -h, --help            show this help message and exit
      -g, --debug           Print debugging information
      --kill-on-failure     Stop at the first failure
      --parse               Print the output using colon separated key=value
                            fields
      -v, --verbose         
      -w WEB_SERVER, --web=WEB_SERVER
                            Specify the autotest server to talk to
      -u USER_FLIST, --ulist=USER_FLIST
                            File listing the users

Listing users
-------------

::

    # autotest-rpc-client user list help
    usage: autotest-rpc-client user list [options] <users>

    options:
      -h, --help            show this help message and exit
      -g, --debug           Print debugging information
      --kill-on-failure     Stop at the first failure
      --parse               Print the output using colon separated key=value
                            fields
      -v, --verbose         
      -w WEB_SERVER, --web=WEB_SERVER
                            Specify the autotest server to talk to
      -u USER_FLIST, --ulist=USER_FLIST
                            File listing the users
      -a ACL, --acl=ACL     Only list users within this ACL
      -l ACCESS_LEVEL, --access_level=ACCESS_LEVEL
                            Only list users at this access level

You can list all the users or filter on specific users, ACLs or access
levels. You can use wildcards for those options. The verbose option
displays the access level.

::

    # Show all users
    # autotest-rpc-client user list 
    Login
    user0
    user1
    me_too
    you_as_well

    # Show all users starting with u
    # autotest-rpc-client user list u\* -v
    Id   Login         Access Level
    3    user0         0
    7    user1         1

    # Show all users starting with u and access level 0.
    # autotest-rpc-client user list u\* -v -l 0
    Id   Login         Access Level
    3    user0         0

    # Show all users belonging to the ACL acl0
    # autotest-rpc-client user list -a acl0
    Login
    user1
    metoo
