==========================
Control file specification
==========================
This document will go over what is required to be in a control file for
it to be accepted into git. The goal of this is to have control files
that contain all necessary information for the frontend/the user to
ascertain what the test does and in what ways it can be modified.

Naming your control files
-------------------------
Control files should always start with **control.XXXXX**, where **XXXXX** is up to you
and the code reviewer, the idea is for it to be short sweet and
descriptive. For example, for 500 iterations of hard reboot test a decent
name would be ``control.hard500``.

Variables
---------
An overview of variables that should be considered required in any control file submitted to our repo.

+--------------------+--------------------------------------------------------------------------------+
| **Name**           | **Description**                                                                |
+--------------------+--------------------------------------------------------------------------------+
| \* AUTHOR          | Contact information for the person or group that wrote the test                |
+--------------------+--------------------------------------------------------------------------------+
| DEPENDENCIES       | What the test requires to run. Comma deliminated list e.g. 'CONSOLE'           |
+--------------------+--------------------------------------------------------------------------------+
| \* DOC             | Description of the test including what arguments can be passed to it           |
+--------------------+--------------------------------------------------------------------------------+
| EXPERIMENTAL       | If this is set to True production servers will ignore the test                 |
+--------------------+--------------------------------------------------------------------------------+
| \* NAME            | The name of the test for the frontend                                          |
+--------------------+--------------------------------------------------------------------------------+
| RUN\_VERIFY        | Whether or not the scheduler should run the verify stage, default True         |
+--------------------+--------------------------------------------------------------------------------+
| SYNC\_COUNT        | Accepts a number >=1 (1 being the default)                                     |
+--------------------+--------------------------------------------------------------------------------+
| \* TIME            | How long the test runs SHORT < 15m, MEDIUM < 4 hours, LONG > 4 hour            |
+--------------------+--------------------------------------------------------------------------------+
| \TEST\_CLASS       | This describes the class for your the test belongs in. e.g. Kernel, Hardware   |
+--------------------+--------------------------------------------------------------------------------+
| \TEST\_CATEGORY    | This describes the category for your tests e.g. Stress, Functional             |
+--------------------+--------------------------------------------------------------------------------+
| \* TEST\_TYPE      | What type of test: client, server                                              |
+--------------------+--------------------------------------------------------------------------------+

\* **Are required for test to be considered valid**

If you'd like to verify that your control file defines these variables
correctly, try the ``utils/check_control_file_vars.py`` utility.

AUTHOR (Required)
~~~~~~~~~~~~~~~~~
The name of either a group or a person who will be able to answer questions pertaining to the test should the 
development team not be able to fix bugs. **With email address included**

DEPENDENCIES (Optional, default: None)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Dependencies are a way to describe what type of hardware you need to find to run a test on. Dependencies are 
just a fancy way of saying if this machine has this label on it then it is eligible for this test. 

An example usecase for this would be if you need to run a test on a device that has bluetooth you would add 
the following to your control file::

   DEPENDENCY = "Bluetooth"

Where ``Bluetooth`` is the exact label that was created in Autotest and has been added to a machine in
Autotest either via the CLI or the Django admin interface. 

DOC (Required)
~~~~~~~~~~~~~~
The doc string should be fairly verbose describing what is required for the test to be run successfully and
any modifications that can be done to the test. Any arguments in your ``def execute()`` that can change the 
behavior of the test need to be listed here with their defaults and a description of what they do.

EXPERIMENTAL (Optional, default: False)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
If this field is set the test import process for the frontend will ignore these tests for production
Autotest servers. This is useful for gettings tests checked in and tested in development servers
without having to worry about them sneaking into production servers.

NAME (Required)
~~~~~~~~~~~~~~~
The name that the frontend will display, this is useful when you have multiple control files for the same
test but with slight variations.

RUN\_VERIFY (Optional, default: True)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
It is used to have the scheduler not run verify on a particular job when it is scheduling it.

SYNC\_COUNT (Optional, default: 1)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
It accepts a number >=1 (1 being the default). If it's 1, then it's a async test. If it's >1 it's sync.

For example, if I have a test that requires exactly two machines ``SYNC_COUNT = 2``. The scheduler will
then find the maximum amount of machines from the job submitted that will run that fit the ``SYNC_COUNT``
evenly.

For example, if I submit a job with 23 machines, 22 machines will run the test in that job and
one will fail to run becase it doesn't have a pair. 

TIME (Required)
~~~~~~~~~~~~~~~
How long the test generally takes to run. This does not include the autotest setup time but just your
individual test's time.

+--------+--------------------------------------+
| TIME   | Description                          |
+========+======================================+
| SHORT  | Test runs for a maximum of 15 minutes|
+--------+--------------------------------------+
| MEDIUM | Test runs for less four hours        |
+--------+--------------------------------------+
| LONG   | Test runs for longer four hours      |
+--------+--------------------------------------+


TEST\_CATEGORY (Required)
~~~~~~~~~~~~~~~~~~~~~~~~~
This is used to define the category your tests are a part of.

Examples of categories:

-  Functional
-  Stress

TEST\_CLASS (Required)
~~~~~~~~~~~~~~~~~~~~~~
This****describes the class type of tests. This is useful if you have different different types of tests you 
want to filter on. If a test is added with a ``TEST_CLASS`` that does not exist the frontend should add that class.

Example tests classes

-  Kernel
-  Hardware

TEST\_TYPE (Required)
~~~~~~~~~~~~~~~~~~~~~
This will tell the frontend what type of test it is. Valid values are **server** and **client**.
Although ``server_async`` jobs are also a type of job in correlation with ``SYNC_COUNT`` this is taken care of.

Example
-------
::

    TIME ='MEDIUM'
    AUTHOR = 'Scott Zawalski ( scott@xxx.com )'
    TEST_CLASS = 'Hardware'
    TEST_CATEGORY = 'Functional'
    NAME = 'Hard Reboot'
    SYNC_COUNT = 1
    TEST_TYPE = 'server'
    TEST_CLASS = 'Hardware'
    DEPENDCIES = 'POWER, CONSOLE'

    DOC = """
    Tests the reliability of platforms when rebooted. This test allows
    you to do a hard reboot or a software reboot.

    Args:
    type: can be "soft" or "hard", default is "hard"
    e.g. job.run_test('reboot', machine, type="soft")
    This control file does a HARD reboot
    """

    def run(machine):
    job.run_test('reboot', machine, type="hard")
    parallel_simple(run, machines)
