===================================================
Using the autotest package management with autoserv
===================================================

This document will go over how to setup your `Global
Configuration <GlobalConfig>`_ to use your Autotest server as a
packaging repository. After that there will be a section going over how
to add another seperate machine as a remote repository for packages.

By setting up packaging in Autotest you can reduce the amount of files
transferred to clients running jobs which generally descreases the
amount of setup time Autotest has to do for clients.

Setting up your Autotest server as a packaging repository
---------------------------------------------------------

This section assumes you already have AFE and TKO running properly as
outlined in the `Autotest Server Install <AutotestServerInstall>`_
documentation, if this isn't the case it is left up to the reader to
ensure Apache is running and able to serve files out of the directory
they reference in the fetch\_locations below.

In order for packaging to work we need to add the following section to
our global config.

::

    [PACKAGES]
    fetch_location: http://your_autotest_server/packages/builtin, http://your_autotest_server/packages/custom
    upload_location: /usr/local/autotest/packages/builtin
    custom_upload_location: /usr/local/autotest/packages/custom/
    custom_download_location: /usr/local/autotest/custom_packages

Explanation:

**fetch\_location:** is what the client uses when downloading tests. The
order that these are listed are the order they are used by the Autotest
client. We have an entry for both custom and builtin tests since
Autotest doesn't directly discern between custom packages and builtin
packages. We keep them separate so we have to list both locations. It is
up to you to keep these separate but we prefer to do this for clarity.

**upload\_location:** /usr/local/autotest/utils/packager.py uses this
location to determine where it needs to upload files. For example when
you run packager.py upload --all all tests profilers and dependencies in
your tree will be archived and copied either via scp or cp (depending on
if it is local or remote)

**custom\_upload\_location:** This is for custom tests and kernels
uploaded through the frontened or via the command line.

**custom\_download\_location:** This is the location where Autotest puts
packages users upload through the frontend before it is uploaded to your
http repository.

Adding a SSH/HTTP Repository
----------------------------

For a remote repository we use SSH and HTTP. SSH For transferring files
to the machine and http to serve the tests to the clients running jobs.
We chose HTTP for lower overhead transfers (for files that are extremely
large).

This step assumes the user is familiar with setting up Apache (At the
very least barebones to serve files) and keyless SSH.

Requirements:

-  Passwordless SSH for the user defined http repo below
-  Apache setup to serve files out of the directory specified below (In
   this case /var/www/packages/builtin)

Using the above PACKAGES section we add in three new pieces of
information

-  fetch\_location:
   `http://your\_http\_repo\_hostname/packages/builtin <http://your_http_repo_hostname/packages/builtin>`_,
   `http://your\_http\_repo\_hostname/packages/custom <http://your_http_repo_hostname/packages/custom>`_
-  upload\_location:
   `ssh://root@your\_http\_repo\_hostname/var/www/packages/builtin <ssh://root@your_http_repo_hostname/var/www/packages/builtin>`_
-  custom\_upload\_location:
   `ssh://root@your\_http\_repo\_hostname/var/www/packages/custom <ssh://root@your_http_repo_hostname/var/www/packages/custom>`_

::

    [PACKAGES]
    fetch_location: http://your_http_repo_hostname/packages/builtin, http://your_http_repo_hostname/packages/custom, http://your_autotest_server/packages/builtin, http://your_autotest_server/packages/custom
    upload_location: /usr/local/autotest/packages/builtin, ssh://root@your_http_repo_hostname/var/www/packages/builtin
    custom_upload_location: /usr/local/autotest/packages/custom/, ssh://root@your_http_repo_hostname/var/www/packages/custom
    custom_download_location: /usr/local/autotest/custom_packages

