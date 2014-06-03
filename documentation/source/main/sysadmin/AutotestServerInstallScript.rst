Autotest Server/Scheduler/WebUI Install script
==============================================

We have developed a script to automate the install steps for the autotest
server, scheduler and web UI on a (Fedora 16/17/RHEL6/Ubuntu) server.
Debian should also work, but it was not tested.

The recommended installation procedure is:

1) Make sure you have a freshly installed system that we support (a VM, for example).

2) Pick this script straight from github

::

    curl -OL https://raw.github.com/autotest/autotest/master/contrib/install-autotest-server.sh

Debian/Ubuntu: don't forget to first install curl with ``apt-get install curl``.

Then make it executable and execute it:

::

    chmod +x install-autotest-server.sh
    ./install-autotest-server.sh

The command above will show you the script options. Usually you'll
want to provide the options -u for the autotest user password, and
-d for the autotest database password. The script is going to set
all passwords, permissions and dependency installing, and it should
log every step of the way, reporting a log file that you can look
at.

::

    # ./install-autotest-server.sh -u password -d password
    15:59:21 INFO | Installing the Autotest server
    15:59:21 INFO | A log of operation is kept in /tmp/install-autotest-server-07-23-2013-15-59-21.log
    15:59:21 INFO | Install started at: Tue Jul 23 15:59:21 BRT 2013
    15:59:21 INFO | /usr/local free 37G
    15:59:21 INFO | /var free 37G
    15:59:21 INFO | Installing git packages
    ...

Hopefully at the end the script will report a URL that you can use to access
your newly installed server. The script should also take care of importing
existing control files, so they appear right away in the server.
