=================
MySQL replication
=================

Introduction
------------

If you're a *heavy* user of Autotest and its reporting/graphing
functionality its possible that you've experienced slow downs that
database slave(s) could mitigate. There are lots of guides on the
internet for doing MySQL replication. This presents just one possible
way to set it up.

Notes on replication:

-  Only read-only operations can go through the slave. At the moment,
   only the new TKO interface supports splitting read-only and
   read-write traffic up between servers.
-  MySQL replicates by replaying SQL statements. This means that it is
   possible to construct SQL statements that will execute
   non-deterministically on replicas. None of the commands Autotest runs
   *should* have this problem, but you need to know it's possible. This
   also means that you might want to verify the consistency of the slave
   database once in a while.
-  MySQL replication happens in one thread. In highly parallelizable,
   write heavy workloads, the slave will probably fall behind. In
   practice this is pretty much never an issue.
-  ...there's lots of other caveats. If you're still reading, you might
   want to check out
   `http://oreilly.com/catalog/9780596101718/ <http://oreilly.com/catalog/9780596101718/>`_

Preparing the Master
--------------------

First of all, you're going to need to set up the binary log. All queries
which might affect the database (i.e. not SELECTs) will be written to
this log. Replication threads will then read the file and send updates
to the database slaves. Because it's in a file, this also means that if
a slave goes off line for a while (under the limit we'll set in a
moment), it can easily re-sync later.

Open the /etc/mysql/my.cnf file with root permissions (so probably with
sudo).

Uncomment out (or add) the following lines in the *[mysqld]* section of
the file.

::

    server-id               = SOMETHING_UNIQUE
    log_bin                 = /var/log/mysql/mysql-bin.log
    expire_logs_days        = 10
    max_binlog_size         = 100M

The server-id needs to be an *unique* 32 bit int but otherwise doesn't
matter. The *log\_bin* says to use binary logging and specifies the
prefix used for log files. The log files are rotated when they become
*max\_binlog\_size* and are kept for *expire\_logs\_days* days.

Restart the mysql server and log into the prompt with the *mysql*
command. Now create a user for replication:

::

    GRANT REPLICATION SLAVE ON *.* TO 'slave_user'@'%' IDENTIFIED BY 'some_password';
    FLUSH PRIVILEGES; 

Creating a Snapshot
-------------------

MySQL has a built in command to sync a slave to a master without any
existing data, but this isn't useful in a production environment because
it locks all the tables on the master for an extended period of time.
The following is a good compromise of downtime (it'll lock things for a
couple minutes) and ease of use. If you can't have any down time,
consult other resources and good luck. :-)

The following command will dump all databases to a file called
/tmp/backup.sql. It uses extended inserts which cuts down on the file
size, but makes the file (a bit) less portable. The --master-data tells
it to write what the current bin-log location is to the beginning of the
file and causes the database to be read-only locked during the duration.

::

    mysqldump -uroot -p --all-databases --master-data --extended-insert > /tmp/backup.sql

Setting up the Slave
--------------------

On the database slave, simply copy over the SQL dump you created in the
last step and (assuming the dump is in /tmp/backup.sql):

::

    mysql -uroot -p < /tmp/backup.sql

Now edit your */etc/mysql/my.cnf*. Add the following lines under the
*[mysqld]* section:

::

    server-id               = SOMETHING_UNIQUE
    log_bin                 = /var/log/mysql/mysql-bin.log
    expire_logs_days        = 10
    max_binlog_size         = 100M
    read_only               = 1

The read\_only parameter makes it so that only DB slave processes and
those with SUPER access can modify the database. The log\_bin turns on
the binary logging so that other servers can be chained off of this
replica.

If you're using a debian based distro, you'll need to copy over the
login data from the */etc/mysql/debian.cnf* of the master to the slave.

Stop and start mysql.

::

    sudo /etc/init.d/mysql stop
    sudo /etc/init.d/mysql start

Out of the SQL dump we loaded earlier, get the master position via

::

    grep  'CHANGE MASTER' /tmp/backup.sql | head -n1

Open up a mysql root prompt and run the following command (modified for
your local setup). After that, start the slave thread and show the
current status.

::

    CHANGE MASTER TO MASTER_HOST='some.host.com', MASTER_USER='slave_user', MASTER_PASSWORD='some_password', MASTER_LOG_FILE='from the output above', MASTER_LOG_POS=ditto;
    START SLAVE;
    SHOW SLAVE STATUS\G;

On your database master, you can run *SHOW MASTER STATUS;' and verify
that the slave is up to date (or is currently catching up).*

