==================================
Autotest status file specification
==================================

General Structure
-----------------

The status file is a variably indented human readable text file format
storing the results or various steps done while running an Autotest job
(ex. reboot start/end, autotest client install, test run/end, etc). The
file is organized by lines and columns, where columns are separated by
TABs. Each line has at least 3 columns:

::

    <command><TAB><subdir><TAB><testname><TAB>....optional content

Note: there must be a trailing <TAB> after the last column on any line

Before the <command> there can be a number of <TAB> characters (also
known as the indentation level).

Formal syntax and semantics specification
-----------------------------------------

The formal definition of the file can be written like this (assuming the
job was not aborted and thus the result file is complete):

::

    <line>
    <line>
    ...
    EOF

Where:

<line> := [<status-line>\|<info-line>\|<group>] # inside a group we can
have status lines, info lines or other groups

<status-line> :=
[<abort-line>\|<alert-line>\|<error-line>\|<fail-line>\|<good-line>\|<warn-line>]

<abort-line> := "ABORT<TAB><subdir-testname><optional-fields>\\n"

<alert-line> := "ALERT<TAB><subdir-testname><optional-fields>\\n"

<error-line> := "ERROR<TAB><subdir-testname><optional-fields>\\n"

<fail-line> := "FAIL<TAB><subdir-testname><optional-fields>\\n"

<good-line> := "GOOD<TAB><subdir-testname><optional-fields>\\n"

<warn-line> := "WARN<TAB><subdir-testname><optional-fields>\\n"

<info-line> := "INFO<TAB><subdir-testname><optional-fields>\\n"

<subdir-testname> := [<none-subdir-testname>\|<valid-subdir-testname>]

<none-subdir-testname> := "----<TAB>----<TAB>"

<valid-subdir-testname> := "<subdir><TAB><valid-testname><TAB>"

<subdir> := \| arbitrary string of characters that does not contain
<TAB>?

<testname> := arbitrary string of characters that does not contain <TAB>
and is not equal to "----"

<optional-fields> := [""\|"<optional-fields-elements><reason><TAB>"] #
optional fields can either be empty or if not must have a reason at the
end which is not key=value syntax

<reason> := string description of a success/failure reason, does not
contain <TAB>

<optional-fields-elements> := [""\|<optional-field-element>] # we may
have a reason but no other optional field

<optional-field-element> :=
"<optional-field-name>=<optional-field-value><TAB><optional-fields-elements>"
# the optional fields to the left of the reason field must be of
key=value syntax

<optional-field-name> := string of characters that do not contain "=" or
<TAB>

<optional-field-value> := string of characters that do not contain <TAB>

<group> := "<start-line><group-contents><end-line>"

<start-line> := "START<TAB><subdir-testname><optional-fields>\\n"

<end-line> := "<end-command><TAB><subdir-testname><optional-fields>\\n"

<end-command> := ["END ABORT"\|"END FAIL"\|"END GOOD"]

<group-contents> := [""\|<group-line>] # a group can be empty

<group-line> := "<TAB><line>"

Definitions:

-  a job group is a group with testname "SERVER\_JOB" or "CLIENT\_JOB"
-  a test group it's a group with testname != "----" that is not a job
   group
-  a base test group is a test group that may be included in a job group
   but is not included in any test group

The formal syntax definition cannot express semantical constraints on
the contents of the file. These are:

-  inside a base test group all valid (that is all values except the
   "----" ones) <testname> columns of any line must be equal to the base
   test group <testname> (that is, there are no sub-tests, once a base
   test group has started everything inside is relevant for that test)
-  a job group is present only once in a result file (ie you can't have
   multiple job groups with the same <testname>)
-  it's invalid to have 2 or more test groups with the same <testname>
   unless one of them includes all the others
-  the next same indentation level END line after a START line shall
   have the same <testname> as its corresponding START line or have
   "----" <testname>
-  it's invalid to have a status-line with "----" subdir and testname
   while not being inside a base test group
-  it's invalid for a <status-line> inside a job group but not inside a
   base test group to have the same <testname> as an active job group
   <testname> unless it's the inner most job group

Parsing Behaviour
-----------------

A violation of the syntactical and semantical constraints shall result
in behaviour as if the next lines in the input buffer after the faulty
line are just a sequence of END ABORT lines ending all the active
(started but not ended) groups having subdir/testname corresponding to
the group they end.

<status-line> parsing:

-  if the line has a valid subdir and we are inside a base test group
   then we update the base test group's subdir
-  if there is no current base test group and if the status line
   <testname> does not refer to an active job group it wil behave as if
   the input buffer has a test group START/END lines with the status
   line testname, subdir, reason, finished time (from the timestamp
   optional field)
-  if there is no current base test group and the status line <testname>
   is equal to an active job group <testname> it will update the status
   of that job group if the <status-line> status is worse in which case
   if there is a reason field it will be used to update the current
   reasons of the referred job group
-  if the status line is inside a base test group it will update that
   group's current status if the new status is worse the the old one and
   finished time (based on the optional timestamp field); if it has
   updated the status and if it has a reason field it will be used to
   update the current reasons of the base test group

A <info-line> parsing can be used to update the current kernel version
if there is such an optional field. The current kernel version is a
parser wide state variable that crosses group boundaries. Can't there be
multiple clients registering INFO for various kernels they boot in the
server server side results file??

When parsing a <end-line> besides ending the current group:

-  the status of the END line (determined by the word after the "END "
   part) will be used to update the current group status
-  if the previous group is a test group with an invalid (ie "----")
   subdir update the subdir of the previous group with the current group
   subdir
-  the finished time of the current group is updated with the timestamp
   of the END line
-  if the end line is for a reboot operation then current kernel version
   is updated with the version from this line
-  if this is the end of a base test group it will be recorded in the db
   with the state, subdir, testname, reasons, finished\_timestamp,
   current kernel version

