=======================
Autotest Unittest suite
=======================

The unittest suite module is the main entry point used to run all the
autotest unit tests. It is important to keep this module running on the
autotest code base to ensure we are not breaking the test coverage we
already got.

Setting up dependencies
-----------------------

This documentation was written for a F18 development box, if you are
running other OS to develop autotest, feel free to add the relevant bits
for your distro.

First, install all dependencies:

::

    sudo installation_support/autotest-install-packages-deps


Now, grab gwt for the dependencies (gwt isn't packaged right now):

::

    utils/build_externals.py


To run the 'short' version of the unittests, just do a:

::

    utils/unittest_suite.py


If you want to run the entire set of unittests, you have to pass the flag --full:

::

    utils/unittest_suite.py --full

