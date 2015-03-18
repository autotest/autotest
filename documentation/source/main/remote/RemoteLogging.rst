======================================
Autoserv message logging specification
======================================

#. All output for the job, and any tests in it should go in ``debug/``
#. All output within a parallel\_simple() subcommand should *also* go in
   ``$hostname/debug`` (for parallel\_simple() over hostnames)
#. All output during any test should *also* go in ``$testname/debug/``
#. We should not buffer beyond one message
#. All lines in the output should be tagged with the logging prefix (for
   multi-line messages, that means one tag per line, so grep works)

   -  the prefix is "[m/d H:M:S level module]", i.e. "[06/08 16:39:17
      DEBUG utils]"

#. All output from subcommands is logged, by default at DEBUG level for
   stdout and ERROR level for stderr
#. All print statements to stdout/stderr get logged with levels DEBUG
   and ERROR respectively. Ideally we'd like to convert all print
   statements into logging calls but that probably won't happen any time
   soon.
#. In each ``debug/`` directory, there are two log files kept:

   -  All debug level messages and above in ``autoserv.stdout``
   -  All error level messages and above in ``autoserv.stderr``

