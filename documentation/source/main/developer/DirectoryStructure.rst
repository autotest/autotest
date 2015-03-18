==============================
Autotest's Directory Structure
==============================

-  **client**: The autotest client. When using the autotest server, the
   entire client dir is deployed to the machine under test.

   -  **shared**: All the files common to both autotest server and
      the client are in this directory. It needs to be here, rather than
      in the top level, because only /client is copied to machines under
      tests. If you add new modules to the shared library. Your library
      will then be importable as ``autotest.client.shared.mylibname``.
   -  **bin**: The autotest core python files are all here. Also, any
      libraries not shared with the server are here.
   -  **tools**: All executables besides autotest itself are here. This
      includes helpers like boottool.
   -  **tests**: All the tests go here. Each test should be in a
      directory, which we'll call ``test_name``. There should also be a
      ``test_name.py`` file in that directory, which is the actual test.
      In addition, a file named ``control`` should also be in that
      directory to run the test with default paramaters. All other files
      the test depends on (and optionally other control files) should be
      in this directory as well.
   -  **site\_tests**: Same as above but for Internal client side tests.
   -  **profilers**: Profilers are here. Profilers run during tests and
      are not tied to any one test.

-  **conmux**: This has conmux, which is a console multiplexer. This
   allows multiple people to share serial concentrators and power
   strips. Several different types of concentrators and strips are
   supported, and new ones can be added by writing simple expect
   scripts.
-  **Documenation**: This wiki is generally more up to date, but there
   are some old diagrams here.
-  **mirror**: This is used for mirroring kernels from kernel.org.
-  **queue**: This is an empty directory used for the file-system based
   queueing system.
-  **results**: This is an empty directory where results can sit.
-  **scheduler**: The scheduler lives here. The scheduler spawns
   autoserv instances to test new kernels.
-  **server**: The autotest server (sometimes called ``autoserv``).
   Unlike the client, all the python files are just in the root dir.
   (Should we move them?)

   -  **doc**: Some documentation files. Unfortunately, these are
      largely out of date. The wiki's your best bet for documenation.
   -  **hosts**: This contains all the host classes. SSHHost is what
      most users will be using.
   -  **tests** and **site\_tests**: These are the same as in the
      client.

-  **tko**: This is the web-based reporting backend for test.kernel.org
-  **ui**: A script for generating control files.

Where should I put the files I'm adding?
----------------------------------------

**Is this a generic module that will be useful on on both the client and
the server?** Then put it in client/shared.  Or, if this module is
providing site-specific functions for use on your local server, add the
name to the libraries variable in client/shared/site\_libraries.

**Are you adding code to the client?** Then put it in client.
Remember that this code will only be accessible from other client code
(and client-side tests), not from server code. Even though the server
has a copy of the client, it generally avoids reaching into the client
to import code (except for a few special cases). If you want to use your
client code from the server as well then put it in the shared library,
not on the client.

**Are you adding code on the server?** If it's a new kind of host, add
it in server/hosts. Be sure to add an import for you new kind of host to
server/hosts/\_\_init.py\_\_, since the server code will import host classes by
pulling in the whole host package, rather than importing classes from
specific submodules.

**Are you adding tests?** Public client side tests should be added in
client/tests/<name>. Private client side tests go in
client/site\_tests/<name>. Server-side tests should go into
server/tests/<name> and again for private server side tests
server/site\_tests/<name>.

