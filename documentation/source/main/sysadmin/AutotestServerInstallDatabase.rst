Autotest Server Install - Set up MySQL
======================================

Let's say you have mysql installed and unconfigured, and that you have chosen
a password, that we'll call MYSQL_ROOT_PASS and a password for the autotest
user, that we'll call MYSQL_AUTOTEST_PASS. The autotest-server-install.sh script
will set them to the same value, but if you are doing things manually, you are
free to choose.

Make sure that mysql daemon is up and starts on each boot. As root:

::

     /sbin/service mysqld restart
     chkconfig mysqld on

The next step is automated through the script autotest-database-turnkey, so
if you want to use it, the process should be as simple as:

::

    /usr/local/autotest/installation_support/autotest-database-turnkey --check-credentials --root-password MYSQL_ROOT_PASS -p MYSQL_AUTOTEST_PASS



If you want to do it manually, provide mysql server with password by running
the following command (as autotest or root, you choose):

::

    mysqladmin -u root password MYSQL_ROOT_PASS


Now, to get a mysql query prompt, type 

::

    mysql -u root -p

The following commands will set up mysql with a read-only user called nobody
and a user with full permissions called autotest with a
password MYSQL_AUTOTEST_PASS, and must be typed on mysql's query prompt:


::

     create database autotest_web;
     grant all privileges on autotest_web.* TO 'autotest'@'localhost' identified by 'MYSQL_AUTOTEST_PASS';
     grant SELECT on autotest_web.* TO 'nobody'@'%';
     grant SELECT on autotest_web.* TO 'nobody'@'localhost';
     create database tko;
     grant all privileges on tko.* TO 'autotest'@'localhost' identified by 'MYSQL_AUTOTEST_PASS';
     grant SELECT on tko.* TO 'nobody'@'%';
     grant SELECT on tko.* TO 'nobody'@'localhost';

If you use *safesync* for migrating the databases you will want to
grant access to the test database. Note that this is entirely optional.

::

    GRANT ALL ON test_autotest_web.* TO 'autotest'@'localhost' identified by 'MYSQL_AUTOTEST_PASS';

If you want mysql available to hosts other than the localhost, you'll
then want to comment out the ``bind-address = 127.0.0.1`` line in the
``/etc/mysql/my.cnf``.

In addition, you may want to increase the
``set-variable = max_connections`` to something like 6000, if you're
running on a substantial server. If you experience scalability issues, you
may want to log slow queries for debugging purposes. This is done with the
following lines:

::

    log_slow_queries = /var/log/mysql/mysql-slow.log  # Log location
    long_query_time = 30  # Time in seconds before we consider it slow

Advanced setups may wish to use
:doc:`MySQL Replication <../frontend/Database/MySQLReplication>`
