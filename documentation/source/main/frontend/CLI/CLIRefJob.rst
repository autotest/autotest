========================================
Job Management - autotest-rpc-client job
========================================

The following actions are used to manage jobs:

::

    # autotest-rpc-client job help
    usage: autotest-rpc-client job [create|list|stat|abort] [options] <job_ids>

    options:
      -h, --help            show this help message and exit
      -g, --debug           Print debugging information
      --kill-on-failure     Stop at the first failure
      --parse               Print the output using colon separated key=value
                            fields
      -v, --verbose         
      -w WEB_SERVER, --web=WEB_SERVER
                            Specify the autotest server to talk to

Creating a Job
--------------

::

    # autotest-rpc-client job create help
    usage: autotest-rpc-client job create [options] job_name

    options:
      -h, --help            show this help message and exit
      -g, --debug           Print debugging information
      --kill-on-failure     Stop at the first failure
      --parse               Print the output using colon separated key=value
                            fields
      -v, --verbose         
      -w WEB_SERVER, --web=WEB_SERVER
                            Specify the autotest server to talk to
      -p PRIORITY, --priority=PRIORITY
                            Job priority (low, medium, high, urgent),
                            default=medium
      -y, --synchronous     Make the job synchronous
      -c, --container       Run this client job in a container
      -f FILE, --control-file=FILE
                            use this control file
      -s, --server          This is server-side job
      -t TESTS, --tests=TESTS
                            Run a job with these tests
      -k KERNEL, --kernel=KERNEL
                            Install kernel from this URL before beginning job
      -m MACHINE, --machine=MACHINE
                            List of machines to run on (hostnames or n*label)
      -M MACHINE_FLIST, --mlist=MACHINE_FLIST
                            File listing machines to use

You can only create one job at a time. The job will be assigned the name
``job_name`` and will be run on the machine(s) specified using the
``-m|--machine|-M|--mlist`` options.

The machines can be specified using their hostnames or if you are just
interested in a specific group of machines, you can use any arbitrary label
you have defined, both platform and non-platform.

The syntax for those is: ``n*label`` to run on ``n``
machines of type ``label`` e.g., ``2*Xeon,3*lab1,hostprovisioning``.
You can omit n if n equals 1.

The options are:

-  ``-p|--priority`` sets the job scheduling priority to Low, Medium
   (default), High or Urgent.

-  ``-s|--server`` specifies if the job is a server job, or a client job
   (default). A server job must specify a control file using the
   ``--control-file`` option.

-  ``-y|--synchronous`` specifies if the job is synchronous or
   asynchronous (default).

-  ``-k|--kernel=<file>`` specifies the URL of a kernel to install
   before running the test(s).

-  ``-c|--container`` runs the test(s) in a container. This is only
   valid for client-side jobs.

The tests can be specified in 2 mutually exclusive ways:

-  ``-f|--control-file=FILE`` will run the job described in the control
   file FILE,
-  ``-t|--tests=a,b,c`` will create a control file to run the tests a,
   b, and c.

One of these 2 options must be present.

The control file must be specified if your job is:

-  synchronous, or
-  a server-side job.

The ``--control-file`` option cannot be used with:

-  the ``--kernel`` option.
-  the ``--container`` option.

If you want to do any of those, code it in the control file itself.

You can find the list of existing tests using ``autotest-rpc-client test list``.

::

    # Create a job my_test using known tests on host0:
    # autotest-rpc-client job create --test dbench,kernbench -m host0 my_test
    Created job:
            my_test (id 6749)

    # Create a server job using a custom control file on host0:
    # cat ./control
    job.run_test('sleeptest')

    # autotest-rpc-client job create --server -f ./control -m host0 my_test_ctrl_file
    Created job:
            my_test_ctrl_file (id 6751)

    # Create a job on 2 Xeon machines, 3 Athlon and 1 x286:
    # Find the platform labels:
    # autotest-rpc-client label list -t
    Name    Valid
    Xeon    True
    Athlon  True
    x286    True

    # autotest-rpc-client job create --test kernbench -m 2*Xeon,3*Athlon,*x286, test_on_meta_hosts
    Created job:
            test_on_meta_hosts (id 6761)

Listing Jobs
------------

::

    # autotest-rpc-client job list help
    usage: autotest-rpc-client job list [options] <job_ids>

    options:
      -h, --help            show this help message and exit
      -g, --debug           Print debugging information
      --kill-on-failure     Stop at the first failure
      --parse               Print the output using colon separated key=value
                            fields
      -v, --verbose
      -w WEB_SERVER, --web=WEB_SERVER
                            Specify the autotest server to talk to
      -a, --all             List jobs for all users.
      -r, --running         List only running jobs
      -u USER, --user=USER  List jobs for given user

You can list all the jobs, or filter on specific users, IDs or job
names. You can use the ``*`` wildcard for the job\_name filter.

::

    # List all my jobs
    # autotest-rpc-client job list
    Id    Owner  Name                  Status Counts
    3590  user0  Thourough test        Aborted:31, Completed:128, Failed:74
    6626  user0  Job                   Completed:1
    6634  user0  Job name with spaces  Aborted:1
    6749  user0  my_test               Queued:1
    6751  user0  my_test_ctrl_file     Queued:1

    # List all jobs starting with 'my'
    # autotest-rpc-client job list my*
    Id    Owner  Name               Status Counts
    1646  user1  myjob              Completed:2
    2702  user2  mytestburnin3      Aborted:1
    6749  user0  my_test            Queued:1
    6751  user0  my_test_ctrl_file  Queued:1

Getting Jobs Status
-------------------

::

    # autotest-rpc-client job stat help
    usage: autotest-rpc-client job stat [options] <job_ids>

    options:
      -h, --help            show this help message and exit
      -g, --debug           Print debugging information
      --kill-on-failure     Stop at the first failure
      --parse               Print the output using colon separated key=value
                            fields
      -v, --verbose
      -w WEB_SERVER, --web=WEB_SERVER
                            Specify the autotest server to talk to
      -f, --control-file    Display the control file

At least one job ID or name must be specified. The ``*`` wildcard can be
used for the job name but **not** for the job ID.

::

    # Get status of the previously queued jobs.  Note the hostname in this output:
    # autotest-rpc-client job stat my_test\*
    Id    Name               Priority  Status Counts  Host Status
    6749  my_test            Medium    Queued:1       Queued:host0
    6751  my_test_ctrl_file  Medium    Queued:1       Queued:host0

    # The stats on a meta host job will show the hostname once the scheduler mapped the platform label to available hosts:

    # autotest-rpc-client job stat 6761
    Id    Name                Priority  Status Counts        Host Status
    6761  test_on_meta_hosts  Medium    Queued:4, Running:1  Running:host42

Aborting Jobs
-------------

::

    # autotest-rpc-client job abort help
    usage: autotest-rpc-client job abort [options] <job_ids>

    options:
      -h, --help            show this help message and exit
      -g, --debug           Print debugging information
      --kill-on-failure     Stop at the first failure
      --parse               Print the output using colon separated key=value
                            fields
      -v, --verbose
      -w WEB_SERVER, --web=WEB_SERVER
                            Specify the autotest server to talk to

You must specify at least one job ID. You cannot use the job name.

::

    # autotest-rpc-client job abort 6749,6751 6761
    Aborted jobs:
            6749, 6751, 6761
