External downloadable tests
===========================
As well as executing built-in tests it is possible to execute external tests. This allows non-standard tests to be constructed
and executed without any requirement to modify the installed Autotest client.

Executing Tests
---------------
A downloadable test is triggered and run in the standard way via the ``run_test`` method, but specifying a URL to a tarball of
the test::

    job.run_test('http://www.example.com/~someone/somewhere/test.tar.bz2')

This will download, install, and execute the test as if it were built-in.

Constructing external downloadable tests
----------------------------------------
External downloadable tests consist of a bzip'ed tarball of the *contents* of a test directory. Things that need to match:

#. The name of the tarball, i.g. ``my_test.tar.bz2``
#. The name of the primary Python file, i.g. ``my_test.py``
#. The name of the test class itself, i.e. ``class my_test(test.test):``

Example::

    $ cat example_test/my_test.py
    from autotest_lib.client.bin import test

    class my_test(test.test):
        version = 1

        def initialize(self):
            print "INIT"

        def run_once(self):
            print "RUN"
    
    $ tar -C example_test -jcvf my_test.tar.bz2 .
    ./
    ./my_test.py

.. note:: You should not pack "example_test" directory but the **contents** of it. Files must be at the *root* of the archive.
