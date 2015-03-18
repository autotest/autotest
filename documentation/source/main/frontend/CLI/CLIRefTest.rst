==========================================
Test Management - autotest-rpc-client test
==========================================

The following actions are available to manage the tests:

::

    # autotest-rpc-client test help
    usage: autotest-rpc-client test list [options] [tests]

    options:
      -h, --help            show this help message and exit
      -g, --debug           Print debugging information
      --kill-on-failure     Stop at the first failure
      --parse               Print the output using colon separated key=value
                            fields
      -v, --verbose
      -w WEB_SERVER, --web=WEB_SERVER
                            Specify the autotest server to talk to
      -T TEST_FLIST, --tlist=TEST_FLIST
                            File listing the tests

Listing Tests
-------------

::

    # autotest-rpc-client test list help
    usage: autotest-rpc-client test list [options] [tests]

    options:
      -h, --help            show this help message and exit
      -g, --debug           Print debugging information
      --kill-on-failure     Stop at the first failure
      --parse               Print the output using colon separated key=value
                            fields
      -v, --verbose
      -w WEB_SERVER, --web=WEB_SERVER
                            Specify the autotest server to talk to
      -T TEST_FLIST, --tlist=TEST_FLIST
                            File listing the tests
      -d, --description     Display the test descriptions

You can list all the tests, or specify a few you'd like information on.

::

    # autotest-rpc-client test list
    Name       Test Type  Test Class
    sleeptest  Client     Canned Test Sets
    dbench     Client     Canned Test Sets
    Kernbench  Client     Canned Test Sets

    # Specifying some test names, with descriptions:
    # autotest-rpc-client test list Kernbench,dbench -d
    Name       Test Type  Test Class        Description
    Kernbench  Client     Canned Test Sets  unknown
    dbench     Client     Canned Test Sets  dbench is one of our standard kernel stress tests.  It produces filesystem
    load like netbench originally did, but involves no network system calls.
    Its results include throughput rates, which can be used for performance
    analysis.

    More information on dbench can be found here:
    http://samba.org/ftp/tridge/dbench/README
