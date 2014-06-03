Virt Test specific configuration
--------------------------------

Important server configuration for virt-test
--------------------------------------------

The way the virt control file is organized right now requires the user to
change one value on global\_config.ini file, that should be at the top
of the autotest tree. 

As autotest, please change the following configuration value
from what's default to make it look like this:

::

     [PACKAGES]
     serve_packages_from_autoserv: False

By default, the above value is True. To make a long story short,
changing this value will make autoserv to copy all tests to the server
before trying to execute the control file, and this is necessary for the
kvm control file to run. Also, we need the other tests present to run
autotest tests inside guests.

Update virt test config files
-----------------------------

Run ``/usr/local/autotest/client/tests/virt/qemu/get_started.py`` as autotest
to be guided through the process of setting up the autotest config files.
Edit the files to suit your testing needs.

The server is now ready to use. Please check out the following sections
to learn how to configure remote hosts and execute the KVM test suite.


Analyze virt job execution results
----------------------------------

The results interface provided by autotest allowing SQL query based filtering,
usable display of logs and test attributes and graphing capabilities.

However, any autotest job also produces a detailed, formatted html report
(**job_report.html**) per remote host tested in addition to standard autotest
logs, where kvm-autotest results data is nicely organized. The html reports are
stored in the job main results directory (accessible via *raw results logs* link).
