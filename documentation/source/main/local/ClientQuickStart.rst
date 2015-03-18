===========================
Autotest Client Quick Start
===========================

The autotest client has few requirements.
Make sure you have python 2.4 or later installed. Also, it is a
good idea to try things in a VM or test machine you don't care
about, for safety.

Download the client wherever you see fit:

::

    git clone --recursive git://github.com/autotest/autotest.git
    cd autotest

Run some simple tests, such our sleeptest, which only sleeps for a given
amount of seconds (our favorite autotest sanity testing).  From the autotest directory
(i.e. /usr/local/autotest/client):

::

    client/autotest-local --verbose run sleeptest

To run any individual test:

::

    client/autotest-local run <testname>

You can also run tests by providing the control file

::

    client/autotest-local client/tests/sleeptest/control

Some tests may require that you run them as root. For example, if you try to run the rtc test as normal user, you will get ``/dev/rtc0: Permission denied error`` in your test result. So you must run the test as root.

**In case you run the client as root, then switch back to a regular
user, some important directories will be owned by root and the next
run will fail. If that happens, you can remove the directories:**

::

    sudo rm -rf client/tmp
    sudo rm -rf client/results

There are sample control files inside the client/samples directory,
useful for learning from.  The kbuild_and_tests/control file in
there will download a kernel, compile it, then reboot the machine
into it.

Execute it as root:

::

    client/autotest-local --verbose client/samples/kbuild_and_tests/control

**WARNING - do it on a test machine, or in a VM, so you don't mess
up your existing system boot configuration**
