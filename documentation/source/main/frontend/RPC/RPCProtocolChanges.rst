===========================================================
Policy for changing the frontend(AFE) and TKO RPC protocols
===========================================================

Try to make any RPC protocol change so that it's backwards compatible.
If there are good reasons not to make it backwards compatible then the
following procedure has to be followed:

-  initial code changes have to be backwards compatible (so we end up
   supporting both old and the new RPC API); existent RPC users in the
   autotest code base have be already changed to use the new API
-  to give enough time for external RPC users, an announcement about
   this RPC change should go on the public mailing list
-  after at least a month since the RPC API change announcement the
   support for the old RPC API can be removed from the code

