ACL Behavior Reference
======================

The following is a reference for the actions that ACLs restrict.

Hosts
-----

-  Users must be in some ACL with a host to modify or delete the host
   and to add the host to an ACL group.

Jobs
----

-  For jobs scheduled against individual hosts, the user must be in some
   ACL with the host.
-  The owner of a job may abort the job. Any other user with ACL access
   to a host can abort that host for any job, *unless* the host is in
   the 'Everyone' ACL.

ACL Groups
----------

-  To add or remove users/hosts in an ACL, the user must be a member of
   that ACL.
-  The 'Everyone' ACL cannot be modified or deleted.
-  When a host is added to an ACL other than 'Everyone', it is
   automatically removed from 'Everyone'. As long as it is a member of
   some other ACL it will always be automatically removed from
   'Everyone'.
-  When a host is removed from all ACL, it is automatically added to
   'Everyone'.

Superusers
----------

Superusers can bypass most of these restrictions. The only thing a
superuser cannot do is delete the 'Everyone' group. To create a
superuser, run the script at
``<autotest_root>/frontend/make_superuser.py``, with the username as a
command-line parameter.

