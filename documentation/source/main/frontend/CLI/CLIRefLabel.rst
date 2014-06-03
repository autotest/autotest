============================================
Label Management - autotest-rpc-client label
============================================

The following actions are available to manage the labels:

::

    #  autotest-rpc-client label help
    usage: autotest-rpc-client label [create|delete|list|add|remove] [options] <labels>

    options:
      -h, --help            show this help message and exit
      -g, --debug           Print debugging information
      --kill-on-failure     Stop at the first failure
      --parse               Print the output using colon separated key=value
                            fields
      -v, --verbose
      -w WEB_SERVER, --web=WEB_SERVER
                            Specify the autotest server to talk to
      -B LABEL_FLIST, --blist=LABEL_FLIST
                            File listing the labels

Creating a label
----------------

::

    # autotest-rpc-client label create help
    usage: autotest-rpc-client label create [options] <labels>

    options:
      -h, --help            show this help message and exit
      -g, --debug           Print debugging information
      --kill-on-failure     Stop at the first failure
      --parse               Print the output using colon separated key=value
                            fields
      -v, --verbose
      -w WEB_SERVER, --web=WEB_SERVER
                            Specify the autotest server to talk to
      -B LABEL_FLIST, --blist=LABEL_FLIST
                            File listing the labels
      -t, --platform        To create this label as a platform

You can create multiple labels at a time. They can be specified on the
command line or in a file, using the ``-B|--blist`` option.

::

    # autotest-rpc-client label create my_label 
    Created label:
            my_label
    # autotest-rpc-client label create label0 label1
    Created label:
            label0, label1

Deleting a label
----------------

::

    # autotest-rpc-client label delete help
    usage: autotest-rpc-client label delete [options] <labels>

    options:
      -h, --help            show this help message and exit
      -g, --debug           Print debugging information
      --kill-on-failure     Stop at the first failure
      --parse               Print the output using colon separated key=value
                            fields
      -v, --verbose
      -w WEB_SERVER, --web=WEB_SERVER
                            Specify the autotest server to talk to
      -B LABEL_FLIST, --blist=LABEL_FLIST
                            File listing the labels

You can delete multiple labels at a time. They can be specified on the
command line or in a file, using the ``-b|--blist`` option.

::

    #  autotest-rpc-client label delete label0,label1
    Deleted labels:
            label0, label1

Listing labels
--------------

::

    # autotest-rpc-client label list help
    usage: autotest-rpc-client label list [options] <labels>

    options:
      -h, --help            show this help message and exit
      -g, --debug           Print debugging information
      --kill-on-failure     Stop at the first failure
      --parse               Print the output using colon separated key=value
                            fields
      -v, --verbose         
      -w WEB_SERVER, --web=WEB_SERVER
                            Specify the autotest server to talk to
      -B LABEL_FLIST, --blist=LABEL_FLIST
                            File listing the labels
      -t, --platform-only   Display only platform labels
      -d, --valid-only      Display only valid labels
      -a, --all             Display both normal & platform labels
      -m MACHINE, --machine=MACHINE
                            List LABELs of MACHINE

You can list all the labels, or filter on specific labels or machines
(exclusively).

::

    # Show all labels
    # autotest-rpc-client label list 
    Name    Valid
    label0  True
    label1  True

    # Display labels that host host0 is tagged with
    # autotest-rpc-client label list label0 -m host0
    Name    Valid
    label0  True

Adding Hosts to a Label
-----------------------

::

    # autotest-rpc-client label add help
    usage: autotest-rpc-client label add [options] <labels>

    options:
      -h, --help            show this help message and exit
      -g, --debug           Print debugging information
      --kill-on-failure     Stop at the first failure
      --parse               Print the output using colon separated key=value
                            fields
      -v, --verbose
      -w WEB_SERVER, --web=WEB_SERVER
                            Specify the autotest server to talk to
      -B LABEL_FLIST, --blist=LABEL_FLIST
                            File listing the labels
      -m MACHINE, --machine=MACHINE
                            Add MACHINE(s) to the LABEL
      -M MACHINE_FLIST, --mlist=MACHINE_FLIST
                            File containing machines to add to the LABEL

You must specify at least one label and one machine.

::

    # Add hosts host0 and host1 to 'my_label'
    # autotest-rpc-client label add my_label -m host0,host1
    Added to label my_label hosts: 
        host0, host1

Removing Hosts from a Label
---------------------------

::

    # autotest-rpc-client label remove help
    usage: autotest-rpc-client label remove [options] <labels>

    options:
      -h, --help            show this help message and exit
      -g, --debug           Print debugging information
      --kill-on-failure     Stop at the first failure
      --parse               Print the output using colon separated key=value
                            fields
      -v, --verbose
      -w WEB_SERVER, --web=WEB_SERVER
                            Specify the autotest server to talk to
      -B LABEL_FLIST, --blist=LABEL_FLIST
                            File listing the labels
      -m MACHINE, --machine=MACHINE
                            Remove MACHINE(s) from the LABEL
      -M MACHINE_FLIST, --mlist=MACHINE_FLIST
                            File containing machines to remove from the LABEL

The options are the same than for adding hosts. You must specify at
least one label and one machine.

::

    # cat my_machines
    host0
    host1,host2
    # autotest-rpc-client label rm my_label --mlist my_machines
    Removed from label my_label hosts:
            host0, host1, host2

    # Completely delete the LABEL.
    # autotest-rpc-client label delete my_label
    Deleted label:
            my_label

Possible errors and troubleshooting
-----------------------------------

::

    Duplicate label: {{{# autotest-rpc-client label create my\_label Operation add\_label
    failed:

    ValidationError?: {'name': 'This value must be unique (my\_label)'}

    }}}

Adding an unknown host:

::

    # autotest-rpc-client label add my_label -m host20,host21
    Operation label_add_hosts failed:
        DoesNotExist: Host matching query does not exist. (my_label (host20,host21))}}}
