Installing an Autotest server (Red Hat version)
================================================

Install script
--------------

We have developed a script to automate the steps described below on a
(Fedora 16/17/RHEL6.2) server. So if you want to save yourself some time,
please check the
:doc:`Installing Server/Scheduler/WebUI notes <../sysadmin/AutotestServerInstallScript>`.

If you want to do it all yourself, we opted by keeping the documentation
herem and we'll do the best to update it. However, we're always working on
streamlining this process, so it might be possible that this can get out of
sync.

If you find any step that might be outdated, please let us know, and we'll
fix it.

Server/Scheduler/Web UI Installation Steps
------------------------------------------

Install required packages
-------------------------

We have automated this step on recent Fedora (17, 18) and RHEL 6, although
it should work on Debian too:

::

    sudo /usr/local/autotest/installation_support/autotest-install-packages-deps

If you want to install it manually here it goes. Keep in mind this can be
outdated, if so we kindly ask your help with keeping it up to date.

.. note::

  Currently autotest is compatible with Django 1.5, so if your
  distribution has anything lower or higher than this version, you
  will have problems and are advised to use a compatible version.

If the distro you are running has Django 1.5 packaged,
you can install the django that your distro ships:

::

     yum install Django


Otherwise, it's best to leave to ``build_externals.py`` the task of installing
it. Other needed packages:

::

     yum install git make wget python-devel unzip
     yum install httpd mod_wsgi mysql-server MySQL-python gnuplot python-crypto python-paramiko java-1.6.0-openjdk-devel python-httplib2
     yum install numpy python-matplotlib libpng-devel freetype-devel python-imaging


Important notes
---------------

**Important:** For this entire documentation, we will assume that you'll
install autotest under /usr/local/autotest. If you use a different path,
please change /usr/local/autotest accordingly. Please that you may have
some issues with apache configuration if you don't choose
/usr/local/autotest.

**Important:** We will also assume that you have created an autotest
user on your box, that you'll use to perform most of the instructions
after the point you have created it. Most of the instructions will use
autotest unless otherwise noted.

Creating the autotest user
--------------------------

As root:

::

     useradd autotest
     passwd autotest [type in new password]

Cloning autotest
----------------

You can then clone the autotest repo (as root):

::

     cd /usr/local
     git clone --recursive git://github.com/autotest/autotest.git
     chown -R autotest:autotest autotest

Log out, re-log as autotest, and then proceed.


Setup MySQL
-----------

Please check the shared
:doc:`Configuring Autotest Server Database notes <../sysadmin/AutotestServerInstallDatabase>`


Install extra packages
----------------------

Run the build script to install necessary external packages. If you ran the
package install script, you should have all you could get from your system
packages and it would download only GWT. As autotest:

::

     /usr/local/autotest/utils/build_externals.py

Always re-run this after a git pull if you notice it has changed, new
dependencies may have been added. This is safe to rerun as many times as you
want. It will only fetch and build what it doesn't already have. It's
important to note that the autotest scheduler will also try to run
build\_externals.py whenever it's executed in order to make sure every piece
of software has the right versions.

**Important**: Set the ``HTTP_PROXY`` environment variable to
`http://proxy:3128/ <http://proxy:3128/>`_ before running the above if
your site requires a proxy to fetch urls.


Update Apache config
--------------------

As root:

::

    ln -s /usr/local/autotest/apache/conf /etc/httpd/autotest.d
    ln -s /usr/local/autotest/apache/apache-conf /etc/httpd/conf.d/z_autotest.conf
    ln -s /usr/local/autotest/apache/apache-web-conf /etc/httpd/conf.d/z_autotest-web.conf

Test your configuration (now with all autotest directives) by running (as root):

::

    service httpd configtest

Now make sure apache will be started on the next boot. If you are running on
a pre-systemd OS, such as RHEL6, you can enable do it this way:

::

    chkconfig --level 2345 httpd on

On a systemd OS (Fedora >= 16), you could do it this way:

::

    systemctl enable httpd.service


Update Autotest config files
----------------------------

**Important:** Edit the following files to match the database passwords
you set earlier during session #Set\_up\_MySQL, as autotest, more specifically,
MYSQL_AUTOTEST_PASS.

::

     /usr/local/autotest/global_config.ini
     /usr/local/autotest/shadow_config.ini

**Important:** Please, do *not* change this field

::

    [AUTOTEST_WEB]
    # Machine that hosts the database
    host: localhost

As we are doing the setup on the same machine where mysql is running, so
*please*, *pretty please* don't change it otherwise you will have trouble
moving forward.

Things that you usually want to change on `global_config.ini`:

Section AUTOTEST\_WEB

::

    # DB password. You must set a different password than the default
    password: please_set_this_password

Section SCHEDULER

::

    # Where to send emails with scheduler failures to
    # (usually an administrator of the autotest setup)
    notify_email:
    # Where the emails seem to come from (usually a noreply bogus address)
    notify_email_from:

Section SERVER

::

    # Use custom SMTP server
    # If none provided, will try to use MTA installed on the box
    smtp_server:
    # Use custom SMTP server
    # If none provided, will use the default SMTP port
    smtp_port:
    # Use custom SMTP user
    # If none provided, no authentication will be used
    smtp_user:
    # Use SMTP password
    # It only makes sense if SMTP user is set
    smtp_password:


Run DB migrations to set up DB schemas and initial data
-------------------------------------------------------

**Important:** If you set up your database using autotest-database-turnkey,
this step can be safely skipped.


During the time span of the project, the autotest database went through
design changes. In order to make it able for people running older
versions to upgrade their databases, we have the concept of migration.
Migration is nothing but starting from the initial database design until
the latest one used by this specific version of the application. As autotest:

::

     /usr/local/autotest/database/migrate.py --database=AUTOTEST_WEB sync

Run Django's syncdb
-------------------

**Important:** If you set up your database using autotest-database-turnkey,
this step can be safely skipped.

You have to run syncdb twice, due to peculiarities of the way syncdb works on
Django. As autotest:

::

     /usr/local/autotest/frontend/manage.py syncdb
     /usr/local/autotest/frontend/manage.py syncdb

Compile the GWT web frontends
-----------------------------

Compile the Autotest web application and TKO frontend. As autotest:

::

     /usr/local/autotest/utils/compile_gwt_clients.py -a

You will need to re-compile after any changes/syncs of the
frontend/client pages.

SELinux Issues
--------------

You may encounter issues with SELinux not allowing a section of the web
UI to work when running in Enforcing Mode. In order to fix this, you can
run the following commands to allow execution of the cgi scripts on your
server.

As root:

::

     semanage fcontext -a -t httpd_sys_script_exec_t '/usr/local/autotest/tko(/.*cgi)?'
     restorecon -Rvv /usr/local/autotest

**Note:** If you are having weird problems with installing autotest, you
might want to turn off SElinux to see if the problem is related to it,
and then think of a sensible solution to resolve it.

Restart Apache
--------------

As root:

::

     /sbin/service httpd restart

Test the server frontend
------------------------

You should be able to access the web frontend at
`http://localhost/afe/ <http://localhost/afe/>`_, or
`http://your.server.fully.qualified.name.or.ip/afe/ <http://your.server.fully.qualified.name.or.ip/afe/>`_

Start the scheduler
-------------------

Executing using old SysV init scripts (RHEL6 and Fedora <= 14)
--------------------------------------------------------------

As root:

::

     cp /usr/local/autotest/utils/autotest-rh.init /etc/init.d/autotestd
     chkconfig --add /etc/init.d/autotestd
     service autotestd start

Executing using systemd (Fedora >= 15)
--------------------------------------

Copy the service file to systemd service directory. As root or using sudo:

::

     sudo cp /usr/local/autotest/utils/autotestd.service /etc/systemd/system/

Make systemd aware of it:

::

     sudo systemctl daemon-reload

Start the service:

::

     sudo systemctl start autotestd.service

Check its status:

::

     autotestd.service - Autotest scheduler
              Loaded: loaded (/etc/systemd/system/autotestd.service)
              Active: active (running) since Wed, 25 May 2011 16:13:31 -0300; 57s ago
              Main PID: 1962 (autotest-schedu)
                CGroup: name=systemd:/system/autotestd.service
                       ├ 1962 /usr/bin/python -u /usr/local/autotest/scheduler/autotest-scheduler-watcher
                       └ 1963 /usr/bin/python -u /usr/local/autotest/scheduler/autotest-scheduler /usr/local/autotest/results

Executing manually using screen (not recommended)
-------------------------------------------------

You can execute the babysitter scripter through, let's say, nohup or
screen. It is important to remember that by design, it's better to
create an 'autotest' user that can run the scheduler and communicate
with the machines through ssh. As root:

::

     yum install screen

As autotest:

::

     screen
     /usr/local/autotest/scheduler/autotest-scheduler-watcher

You can even close the terminal window with screen running, it will keep
the babysitter process alive. In order to troubleshoot problems, you can
pick up the log file that autotest-scheduler-watcher prints and follow it
with tail. This way you might know what happened with a particular
scheduler instance.

Client Installation Steps
-------------------------

Clients are managed in the tab hosts of the web frontend. It is important
that you can log onto your clients from your server using ssh *without*
requiring a password.

Setup password-less ssh connection from the server to this host (client)
------------------------------------------------------------------------

As autotest, on the server, create a RSA key in the following way:

::

     ssh-keygen -t rsa

Then, still on the server, and as autotest, copy it to the host:

::

     ssh-copy-id root@your.host.name


Import tests data into the database
-----------------------------------

You can import all the available tests inside the autotest client dir by
running the test importer script as autotest:

::

     /usr/local/autotest/utils/test_importer.py -A


If you did clone the autotest repo with --recursive, the virt test will be
among the imported tests.


Troubleshooting your server
---------------------------

You can refer to the
`Autotest Troubleshooting Documentation <../sysadmin/AutotestServerTroubleshooting>`
documentation for some commonly reported problems and their root causes.


Virt Test specific configuration
--------------------------------

Please refer to the shared `Autotest Virt Documentation <../sysadmin/AutotestServerVirt>`

See also
--------

-  `The Parser <../scheduler/Parse>` is used to import results into TKO
-  `The Web Frontend Docs <../sysadmin/WebFrontendHowTo>` talks about using the
   frontend
-  `The Web Frontend Development Docs <../developer/WebFrontendDevelopment>`
   talks about setting up for frontend development work - you do not want to
   develop through Apache!
