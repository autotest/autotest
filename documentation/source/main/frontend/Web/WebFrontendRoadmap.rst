====================
Web Frontend Roadmap
====================

There are currently two completely separate projects with Autotest that
might be called web frontends:

-  the Autotest Frontend or AFE project is a GUI for managing jobs and
   hosts, including creation of new jobs and tracking queued and running
   jobs. It lives under the "frontend" directory. This is frequently
   referred to as simply "the web frontend".
-  the TKO project is a GUI for results reporting. It allows the user to
   view summarized test results across many jobs, filtered and grouped
   by various categories. It lives under the "new\_tko" directory.

AFE
---

There are a few medium-sized features we'd like to complete:

-  Implement complete ACL support -- *partially done* ACL support is
   barely implemented right now -- ACL-inaccessible hosts are hidden
   from the user in the GUI host list, and meta-hosts are blocked from
   being scheduled on inaccessible hosts. We need to add proper support
   for blocking the scheduling of inaccessible hosts, including support
   for superusers. We need ACL protection for aborting jobs and for
   modifying hosts.

-  Creating jobs using previous jobs as templates -- **done** When the
   "Requeue job" is clicked, instead of immediately creating a new job,
   the user will be taken to the "Create Job" tab. All the info from the
   old job will be filled in. The user will then have the option of
   making changes before submitting the new job.

-  Easier management of many items (jobs + host) -- **done** Currently,
   to abort many jobs, the user must click each job individually to go
   to its job detail page and then click the "Abort job" button. We'd
   like to allow the user to select many jobs in the job list page and
   then abort them all at once. Similar functionality could be used on
   the host list page to, for instance, send many hosts into repair.

-  Better linking directly to raw logs (job + host logs) -- **done**
   Jobs are often triaged by looking at the raw results logs. The only
   link to these from the frontend is the one "raw results logs" link on
   the job detail page, which takes the user to the root results
   directory for the job. The host queue entries table on the job detail
   tab should contain links to the debug logs for each host, and the
   host detail page should link to the host log for each host.

-  Parsing and using information from control files - **done** The
   frontend should be able to parse information such as test types and
   descriptions from control files and put this information into the
   database. The frontend should display or use this information as
   appropriate. Most of it is already used or displayed, but some of
   this could be improved, such as the display of test descriptions
   (currently done with tooltips).

Larger features we'd like to have include:

-  Host management features We'd like the Autotest frontend to have more
   powerful features for managing a large pool of hosts, including
   tracking of machine health and better support for machine repairs.

-  Port admin interface to GWT Addition, modification and deletion of
   hosts, labels and tests is currently done through the Django admin
   interface. We'd like to port this functionality to GWT so that we can
   better customize it and integrate it with the rest of the frontend.

TKO
---

See `TkoWebRequirements <TkoWebRequirements>`_ for reference.

Stage 1
~~~~~~~

**done** Basic spreadsheet view including all features of old TKO
interface (or equivalent newer versions)

-  SQL filtering conditions
-  Row and column field selection
-  Left-click default drilldown (single test cells go straight to logs
   instead of test detail view)
-  Floating headers

Stage 2
~~~~~~~

**done** Enhanced spreadsheet features

-  Right-click menu with drilldown options (and table-wide actions menu
   at top)
-  Multiple cell selection
-  Test labels

Stage 3
~~~~~~~

**done** Table view

-  Column selection + ordering
-  Grouping feature
-  Left- and right-click actions
-  Sorting
-  Job triage options from spreadsheet view

Stage 4
~~~~~~~

*never got implemented* User-friendly filtering

-  Filter widgets mode
-  Filtering widgets for all fields
-  Conversion to SQL with custom editing allowed

Longer term
~~~~~~~~~~~

Plotting functionality and test detail view **both done**

