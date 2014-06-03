=======================
TKO parse documentation
=======================

::

    usage: parse [options]

    options:
      -h, --help  show this help message and exit
      -m          Send mail for FAILED tests
      -r          Reparse the results of a job
      -o          one: parse a single results directory
      -l LEVEL    levels of subdirectories to include in job name

Typical usages:

To populate the database with ALL results.

::

    tko/parse $AUTODIR/results

To recreate the database (from some corruption, etc). First drop all the
tables, and recreate them. Then run:

::

    tko/parse -r $AUTODIR/results

To reparse a single job's results

::

    tko/parse -r -o $AUTODIR/results/666-me

To reparse a single machine's results within a job:

::

    tko/parse -r -l 2 -o $AUTODIR/results/666-me/machine1

The -l2 here makes it create the job as "666-me/machine1" instead of
"machine1", which is normally what we want. it just says "take the last
2 elements of the path, not the last one".

