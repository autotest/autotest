==================
Custom RPC Scripts
==================

This is a brief outline of how to use the TKO RPC interface to write
custom results analysis scripts in Python. Using the AFE RPC interface
is very similar.

Basically:

-  make your script any place in the client with a common.py
-  to import the rpc stuff you need do:

   ::

       import common
       from autotest_lib.cli import rpc

-  to create the object you need for making the rpc calls use "comm =
   rpc.tko\_comm()"; you can pass in a host name if you want to point at
   something other than what's in the global\_config.ini file in your
   client.
-  you can get the test detail with code like:

   ::

       test_views = comm.run("get_detailed_test_views", ...filters go here...)

   The filters are basically django filters. I won't go into much detail
   here, the obvious ones you'd want to use are:

   -  job\_tag\_\_startswith - set it to something like "1234-" to get
      data on job 1234
   -  hostname - if you want data for a specific hostname, set this
   -  test\_name - if you want data for a specific test name, set this

        So you could do something like:

        ::

            test_views = comm.run("get_detailed_test_views", job_tag__startswith="1234-", hostname="myhost")

The test\_views returned by that call is a list of dictionaries, one
dictionary for each test returned by the call. The main keys you're
concerned with will be "attributes" and "iterations".

attributes is a dictionary of all the test level keyvals - you can see
stuff like "sysinfo-uname" here.

iterations is a list of dictionaries, one for each iteration. Each
dictionary has two entries; an "attr" one, which is a dictionary of all
the key{attr}=value attributes in the test, and a "perf" one, which is a
dictionary of all the key{perf}=value attributes.

And...that's basically how you access all that info. You make that call
and get a big list of dictionaries. Oh, and avoid calling it without
filters; trying to pull down data for every single test can be a bad
idea (depending on the size of your database).

