.. image:: https://badge.waffle.io/autotest/autotest.png?label=ready&title=Ready 
 :target: https://waffle.io/autotest/autotest
 :alt: 'Stories in Ready'
========================================================
Autotest: Fully automated tests under the linux platform
========================================================

Autotest is a framework for fully automated testing. It is designed primarily to
test the Linux kernel, though it is useful for many other functions such as
qualifying new hardware. It's an open-source project under the GPL and is used
and developed by a number of organizations, including Google, IBM, Red Hat, and
many others.

Autotest is composed of a number of modules that will help you to do stand alone
tests or setup a fully automated test grid, depending on what you are up to.
A non extensive list of modules is:

* Autotest client: The engine that executes the tests (dir client). Each
  autotest test is a directory inside (client/tests) and it is represented
  by a python class that implements a minimum number of methods. The client
  is what you need if you are a single developer trying out autotest and executing
  some tests. Autotest client executes ''client side control files'', which are
  regular python programs, and leverage the API of the client.

* Autotest server: A program that copies the client to remote machines and
  controls their execution. Autotest server executes ''server side control files'',
  which are also regular python programs, but leverage a higher level API, since
  the autotest server can control test execution in multiple machines. If you
  want to perform tests slightly more complex involving more than one machine you
  might want the autotest server

* Autotest database: For test grids, we need a way to store test results, and
  that is the purpose of the database component. This DB is used by the autotest
  scheduler and the frontends to store and visualize test results.

* Autotest scheduler: For test grids, we need an utility that can schedule and
  trigger job execution in test machines, the autotest scheduler is that utility.

* Autotest web frontend: For test grids, A web app, whose backend is written in
  django (http://www.djangoproject.com/) and UI written in gwt
  (http://code.google.com/webtoolkit/), lets users to trigger jobs and visualize
  test results

* Autotest command line interface: Alternatively, users also can use the
  autotest CLI, written in python


Getting started with autotest client
------------------------------------

For the impatient:

http://autotest.readthedocs.org/en/latest/main/local/ClientQuickStart.html

Installing the autotest server
------------------------------

For the impatient using Red Hat:

http://autotest.readthedocs.org/en/latest/main/sysadmin/AutotestServerInstallRedHat.html

For the impatient using Ubuntu/Debian:

http://autotest.readthedocs.org/en/latest/main/sysadmin/AutotestServerInstall.html

You are advised to read the documentation carefully, specially with details
regarding appropriate versions of Django autotest is compatible with.

Main project page
-----------------

http://autotest.github.com/


Documentation
-------------

Autotest comes with in tree documentation, that can be built with ``sphinx``.
A publicly available build of the latest master branch documentation and
releases can be seen on `read the docs <https://readthedocs.org/>`__:

http://autotest.readthedocs.org/en/latest/index.html

It is possible to consult the docs of released versions, such as:

http://autotest.readthedocs.org/en/0.16.0/

If you want to build the documentation, here are the instructions:

1) Make sure you have the package ``python-sphinx`` installed. For Fedora::

    $ sudo yum install python-sphinx

2) For Ubuntu/Debian::

    $ sudo apt-get install python-sphinx

3) Optionally, you can install the read the docs theme, that will make your
   in-tree documentation to look just like in the online version::

    $ sudo pip install sphinx_rtd_theme

4) Build the docs::

    $ make -C documentation html

5) Once done, point your browser to::

    $ [your-browser] docs/build/html/index.html


Mailing list and IRC info
-------------------------

http://autotest.readthedocs.org/en/latest/main/general/ContactInfo.html


Grabbing the latest source
--------------------------

https://github.com/autotest/autotest


Hacking and submitting patches
------------------------------

http://autotest.readthedocs.org/en/latest/main/developer/SubmissionChecklist.html


Downloading stable versions
---------------------------

https://github.com/autotest/autotest/releases


Next Generation Testing Framework
---------------------------------
Please check Avocado, a next generation test automation framework being
developed by several of the original Autotest team members:

http://avocado-framework.github.io/
