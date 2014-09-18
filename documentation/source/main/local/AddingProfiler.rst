Using and developing job profilers
==================================
Adding a profiler is much like adding a test. Each profiler is completely
contained in it's own subdirectory (under ``client/profilers`` or
if you just checked out the client - under ``profilers/``) - the normal
components are:

-  An example control file, e.g. ``profilers/myprofiler/control``.
-  A profiler wrapper, e.g. ``profilers/myprofiler.py``.
-  Some source code for the profiler (if it's not all done in just the
   Python script)

Start by taking a look over an existing profiler. I'll pick ``readprofile``,
though it's not the simplest one, as it shows all the things you might
need. Be aware this one will only work if you have ``readprofile`` support
compiled into the kernel.

The control file is trivial, just ::

    job.profilers.add('readprofile')
    job.run_test('sleeptest', 1)
    job.profilers.delete('readprofile')

That just says "please use readprofile for the following tests". You can
call ``profilers.add`` multiple times if you want multiple profilers at
once. Then we generally just use *sleeptest* to do a touch test of
profilers - it just sleeps for N seconds (1 in this case).

There's a tarball for the source code - *util-linux-2.12r.tar.bz2* - this
will get extracted under ``src/`` later. Most of what you're going to have
to do is in the python wrapper. Look at ``readprofile.py`` - you'll see it
inherits from the main profiler class, and defines a version (more on
that later). You'll see several functions:

- ``setup()`` - This is run when you first use the profiler, and normally is used to compile the source code.
- ``intialize()`` - This is run whenever you import the profiler.
- ``start()`` - Starts profiling.
- ``stop()`` - Stops profiling.
- ``report()`` - Run a report on the profiler data.

Now let's look at those functions in some more detail.

Setup
-----
This is the one-off setup function for this test. It won't run again unless you change the version number
(so be sure to bump that if you change the source code). In this case it'll extract
*util-linux-2.12r.tar.bz2* into ``src/``, and compile it for us. Look at the first few lines::

   # http://www.kernel.org/pub/linux/utils/util-linux/util-linux-2.12r.tar.bz2
   def setup(self, tarball = 'util-linux-2.12r.tar.bz2'):
      self.tarball = unmap_url(self.bindir, tarball, self.tmpdir)
      extract_tarball_to_dir(self.tarball, self.srcdir)

A comment saying where we got the source from. The function header - defines what the default tarball to 
use for the source code is (you can override this with a different version from the control file if you
wanted to, but that's highly unusual). Lastly there's some magic with ``unmap_url`` - that's just incase
you overrode it with a URL - it'll download it for you, and return the local path just copy that bit. ::

   os.chdir(self.srcdir)
   system('./configure')
   os.chdir('sys-utils')
   system('make readprofile')

OK, so this just extracts the tarball into ``self.srcdir`` (pre-setup for you to be src/ under the profiler),
cd's into that src dir, and runs ``./configure`` and then just makes the readprofile component
(util-linux also contains a bunch of other stuff we don't need) - just as you would for most standard
compilations. Note that we use the local ``system()`` wrapper, not ``os.system()`` - this will automatically
throw an exception if the return code isn't 0, etc.

Initialize
----------
::
   
   def initialize(self):
      try:
         system('grep -iq " profile=" /proc/cmdline')
      except:
            raise CmdError, 'readprofile not enabled'

      self.cmd = self.srcdir + '/sys-utils/readprofile'

This runs whenever we import this profiler - it just checks that ``readprofile`` is enabled,
else it won't work properly.

Start
-----
::

   def start(self, test):
      system(self.cmd + ' -r')

Start the profiler! Just run ``readprofile -r``.

Stop
----
::

   def stop(self, test):
      # There's no real way to stop readprofile, so we stash the
      # raw data at this point instead. BAD EXAMPLE TO COPY! ;-)
      self.rawprofile = test.profdir + '/profile.raw'
      print "STOP"
      shutil.copyfile('/proc/profile', self.rawprofile)

Normally you'd just run ``readprofile --stop``, except this profiler doesn't seem to have that. 
We want to do the lightest-weight thing possible, in case there are multiple profilers running,
and we don't want them to interfere with each other.

Report
------
::

   def report(self, test):
      args  = ' -n'
      args += ' -m ' + get_systemmap()
      args += ' -p ' + self.rawprofile
      cmd = self.cmd + ' ' + args
      txtprofile = test.profdir + '/profile.text'
      system(cmd + ' | sort -nr > ' + txtprofile)
      system('bzip2 ' + self.rawprofile)

This just converts it into text. We need to find this kernel's ``System.map`` etc (for which there's a helper),
and then produce the results in a useful form (in this case, a text file). 
Note that we're passed the test object, so we can store the results under the ``profiling/``
subdirectory of the test's output by using the test.profdir which has been set up automatically for you.

Adding your own profiler
------------------------
Now just create a new subdirectory under ``profilers``, and add your own control file, source code, and wrapper.
It's probably easiest to just copy ``readprofile.py`` to ``mytest.py``, and edit it - remember to change the
name of the class at the top though.

If you have any problems, or questions, drop an email to the
`Autotest mailing list <http://www.redhat.com/mailman/listinfo/autotest-kernel>`_, and we'll help you out.
