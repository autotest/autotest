======================
Host Protection Levels
======================

Host protection levels are used to protect particular hosts from actions
that occur during the verify and repair phases. These can be set using
the CLI or the frontend admin interface. They are defined in
``client/common_lib/host_protections.py`` and contained in the
``protection`` field of the ``hosts`` table in the ``autotest_web``
database.

-  **No protection** -- anything can be done to this host.
-  **Repair software only** -- any software problem can be fixed,
   including a full machine reinstall.
-  **Repair filesystem only** -- the filesystem can be cleaned out, but
   not system reconfiguration or reinstall can occur.
-  **Do not repair** -- do not attempt any repair on the machine.
-  **Do not verify** -- do not verify or repair the machine (the machine
   will be assumed to be in working order).

