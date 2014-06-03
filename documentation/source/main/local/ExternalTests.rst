===========================
External Downloadable Tests
===========================

As well as executing builtin tests it is possible to execute external
tests. This allows non-standard tests to be constructed and tested
without any requirement to modify the installed autotest client.

Executing Tests
---------------

A downloadable test is triggered and run in the standard way via the
run\_test method, but specifying a URL to a tarball of the test:

::

    job.run_test('http://www.example.com/~someone/somewhere/test.tar.bz2')

This will download, install, and execute the test as if it were builtin.

Constructing external downloadable tests
----------------------------------------

External downloadable tests consist of a bzip'ed tarball of the
*contents* of a test directory. Things that need to match:

#. The name of the tarball
#. The name of the primary ``.py`` file
#. The name of the test class itself

Example:

::

    $ cat foo/foo.py
    from autotest_lib.client.bin import test

    class foo(test.test):
        version = 1

        def initialize(self):
            print "INIT"

        def run_once(self):
            print "RUN"
    $ tar -C foo -jcvf foo.tar.bz2 .
    ./
    ./foo.py
    $ 

Again, notice that you should not pack "foo" dir but the contents of it.
Files must be at the "root" of the package.

