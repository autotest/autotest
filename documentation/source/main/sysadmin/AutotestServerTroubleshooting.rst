Autotest Server Troubleshooting
===============================

Here we have some common problems in the server/scheduler/web UI and solutions
for thems. Also, we have info on log files you can look after.

Checking scheduler logs
-----------------------

You can find them in the autotest logs directory. As autotest or root:

::

     tail -f /usr/local/autotest/logs/scheduler-[timestamp].log

Status is queing
----------------

The scheduler is not running. You are strongly advised to use the init
scripts mentioned in the AutotestServerInstall or AutotestServerInstallRedHat
documentation. If you are using them, restarting the scheduler should be simple:

::

    service autotestd start


Status is pending
-----------------

Usually it is a result of scheduler crash due to lack of disk space on
Autotest server, so you might want to check that.
