========================================
Autotest server interaction with clients
========================================

Tests can be run on standalone machines, or in a server-client mode.

The server interaction is simple:

-  Copy the control file across
-  Execute the control file repeatedly until it completes
-  Client notifies server of any reboot for monitoring
-  Upon completion of control script, server pulls results back (not
   client push)

All interaction with the server harness will be via the *harness*
object. This object provides for a per harness interface. A null
interface will be provided for standalone use.
