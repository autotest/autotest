===================================
Autotest Code Submission Check List
===================================

This document describes to contributors what we are looking for when we
go through submitted patches. Please try to follow this as much as
possible to save both the person reviewing your code as well as yourself
some extra time.

Github Pull Requests
--------------------

In order to keep code review in one place, making the work of our maintainers
easier, we decided to make pull requests the primary means to contributing to
all projects inside the autotest umbrella.

That means it is highly preferrable to send pull requests, rather than patches
to the mailing list. If you feel strongly against using pull requests, we'll
take your patches, but please consider using the recommended method, as it is
considered nicer with the maintainers.

This `documentation on github pull requests <https://help.github.com/articles/using-pull-requests>`_
is complete and up to date, it'll work you through all details necessary. The
bottom line is that you'll fork virt-test or autotest_remote_unittest, create
a working branch, push changes to this branch and then go to the web interface
to create the request.


Subscribe to the mailing list
-----------------------------

That's important. See the link in :doc:`the contact info documentation <../general/ContactInfo>`.
Even though we don't use the mailing list for patch review, we still discuss
RFCs and send announcements to it.

Running Unit tests
------------------

Regardless of what you change it is recommended that you not only add
unittests but also run the unittest suite of each project to
be sure any changes you made did not break anything. In order to install
all the deps required for unittests, please check
:doc:`the unittest suite docs <../developer/UnittestSuite>`.


Example (autotest):

::

    [foo@bar autotest]$ utils/unittest_suite.py --full
    Number of test modules found: 65
    [... lots of output ...]
    All passed!

Example (virt-test):

::

    [foo@bar virt-test]$ tools/run_unittests.py --full
    Number of test modules found: 22
    [... lots of output ...]
    All passed!


Running pylint
--------------

Another tool we use to insure the correctness of our code is pylint. Due
to the way imports have been implemented in the autotest code base a
special wrapper is required to run pylint.

The file is located in ``utils/run_pylint.py``. The virt-test version is in
``tools/run_pylint.py``.

Simply run the command from your code directory and the rest is taken
care of.

Example of running on a source file with warnings:

::

    [lmr@freedom autotest]$ utils/run_pylint.py -q client/job.py

Good. Same process, now with an error I introduced:

::

    [lmr@freedom autotest]$ utils/run_pylint.py -q client/job.py
    ************* Module client.job
    E0602:175,14:base_client_job._pre_record_init: Undefined variable 'bar'

Here is the error, an undefined variable:

::

    [lmr@freedom autotest]$ git diff
    diff --git a/client/job.py b/client/job.py
    index c5e362b..8d335b4 100644
    --- a/client/job.py
    +++ b/client/job.py
    @@ -172,6 +172,7 @@ class base_client_job(base_job.base_job):
             As of now self.record() needs self.resultdir, self._group_level,
             self.harness and of course self._logger.
             """
    +        foo = bar
             if not options.cont:
                 self._cleanup_debugdir_files()
                 self._cleanup_results_dir()


So, pylint is a valuable ally here, use it!

Running reindent.py
-------------------

Yet another tool that we use to fix indentation inconsistencies
(important thing to notice when you're doing python code) is
``utils/reindent.py`` (autotest) or ``tools/reindent.py`` (virt-test).
You can use the script giving your files as an argument, so it will prune
trailing whitespaces from lines and fix incorrect indentation.


Breaking up changes
-------------------

-  Submit a separate patch for each logical change (if your description
   includes "add this, fix that, remove three other unrelated things";
   probably bad).
-  Put a summary line at the very top of the commit message, explaining
   briefly what has changed and where.
-  Put cleanups in separate patches than functional changes.
-  *Please* set up your git environment properly, and always sign your
   patches using commit -s.


Patch Descriptions
------------------

Patch descriptions need to be as verbose as possible. Some of
these points are obvious but still worth mentioning. Describe:

-  The motivation for the change - what problem are you trying to fix?
-  High level description / design approach of how your change works
   (for non-trivial changes)
-  Implementation details
-  Testing results

Follow control file specification
---------------------------------

All tests must follow the control file specification Refer to the
:doc:`Control Requirements section <../local/ControlRequirements>`. In virt-test, you don't
usually need to write control files, so feel free to skip this if you're developing
virt-test.

Follow Coding Style
-------------------

Autotest and virt-test (mostly) follow PEP8, but it's always good to take a
look `at the coding style documentation <https://github.com/autotest/autotest/blob/master/CODING_STYLE>`_.


Git Setup
---------

Please make sure you have git properly setup. We have a fairly brief and descriptive
document explaining how to get the basics :doc:`setup here <GitWorkflow>`. In
particular, tend to stick to one version of your written name, so all your
contributions appear under a same name on git shortlog. For example:

John Doe Silverman

or

John D. Silverman

Please *do choose* between one of them when sending patches, for consistency.


Example Patch
-------------

This is a good example of a patch with a descriptive commit message.

::

    commit 37fe66bb2f6d0b489d70426ed4a78953083c7e46
    Author: Nishanth Aravamudan <nacc@linux.vnet.ibm.com>
    Date:   Thu Apr 26 03:38:44 2012 +0000

        conmux/ivm: use immediate reboot rather than delayed

        Delayed reboots use EPOW, which does not always result in a shutdown of
        the LPAR. Use the more sever immediate shutdown, to ensure the LPAR goes
        down. This matches the HMC code.

        Signed-off-by: Nishanth Aravamudan <nacc@us.ibm.com>
