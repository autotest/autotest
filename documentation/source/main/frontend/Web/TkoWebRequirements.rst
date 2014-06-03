==============================
TKO Web Interface Requirements
==============================

The TKO web interface is a system to generate customizable reports
summarizing test results across many jobs. Whereas AFE focuses on
displaying execution status of indivudual jobs, TKO focuses on
displaying pass/fail results for individual tests. It has options for
filtering out various subsets of test results, grouping test results
along various dimensions, and displaying the results in different ways.

The new TKO UI will be a dynamic web application broadly resembling AFE.
Like AFE, the interface will be divided into tabs.

Overview
~~~~~~~~

-  There will be four main tabs: **spreadsheet view**, **table view**,
   **plotting view**, and **test details**.
-  To the right of these tabs will be a refresh button, followed by a
   **"Saved queries"** drop-down box. This box will allow the user to
   save a particular view, including which tab is being viewed, the
   filtering conditions, and any parameters configuring the display. The
   box will display a list of saved queries for the user as well as an
   option to save a new query. Queries will have history support (see
   below), so they can be shared via URLs (i.e. something like
   `http://myautotestserver/tko/#saved\_query\_1234 <http://myautotestserver/tko/#saved_query_1234>`_).
-  To the right of the saved queries will be a **"Download CSV"** link.
-  The interface will have full **history support**. This will including
   changing the browser title when changing certain view parameters.
   This provides two benefits:

   -  users can share reports by copy-pasting URLs.
   -  browser history will serve as a useful way to navigate among
      recent queries.

Filtering conditions
~~~~~~~~~~~~~~~~~~~~

-  All TKO activities involving filtering down to some subset of all
   recorded test data. All views will share a common interface for
   specifying these conditions. There will be two ways to specify these
   conditions: via **filtering widgets** for each field, or via a single
   **custom SQL** text area. The custom SQL text area is the analogue of
   the condition text box in the old TKO interface.
-  The UI will default to filtering widgets, with a button to go to
   custom SQL mode. When switching to custom SQL, the current widget
   selections will be converted to SQL. The widgets will be replaced
   with a single text area, in which the user can then edit the SQL
   condition. She may also click the button to start with and write a
   SQL condition from scratch. Edited SQL can not be converted back to
   widgets -- changes will have to be reverted. This is analogous to the
   "Edit control file" button in AFE.
-  Filtering widgets mode will initially display a drop-down box of
   fields on which to filter. This list includes **hostname, host
   keyval, host labels, job name, job tag, failure reason, test keyval,
   test labels, test name, test status, time queued, time started, time
   completed, user**.
-  Selecting a field from the drop-down will display a selection widget
   for that field. The widget varies with the field. For most fields,
   there will be a **pair of list boxes** displaying the available and
   selected values for the field. For some fields, there will be an
   alternative option to enter a **regex** to match. Some fields may be
   completely different (i.e. time fields will allow the user to define
   ranges via start and end times, with calendar- and clock-like helper
   widgets available).
-  To the right of each filter widget will be "+" and "-" buttons,
   allowing the user to **add another filter** and **delete the given
   filter**, respectively.

Spreadsheet view
~~~~~~~~~~~~~~~~

-  This view is the future version of what the existing TKO interface
   does. It allows the user to group by two fields, one for row headers
   and one for column headers. It then displays counts of passed test
   runs and all test runs within each grouping.
-  **Incomplete (queued and running) tests** are included in the
   spreadsheet, unless filtered out.
-  At the top, below the filtering area, will be a drop-down box to
   select the **row** and **column** grouping fields. This is just like
   the old TKO interface. Below each box will be a **"Customize
   rows/columns..."**' link, which will expand to allowing the user to
   do two things:

   -  select multiple fields for row or column headers to create
      **composite headers** (and customize the field ordering)
   -  customize ordering of row and column values.

-  Just above the spreadsheet will be a drop-down box with **table-wide
   actions**. It will resemble the right-click context menus (see
   below).
-  The displayed spreadsheet will look similar to how it does today, but
   will have **floating row and column headers**, much like Excel or
   Google Spreadsheets.
-  Left-clicking on a cell will perform a *default drilldown* operation
   as it does in the old interface.
-  Right-clicking on a cell will bring up a **context menu**.

   -  Cells with multiple test runs will have a number of **drill down
      options** first, showing different combinations of row-column
      fields to drilldown to.
   -  Cells with a single test run will have a single option at the top
      to **view test details** (this is the default drilldown option).
      This will bring the user to the test details tab.
   -  All cells will have an option to **switch to table view**, to
      **triage failures** (see below), and to **apply or remove a
      label**. Apply/remove label will bring up a small dialog allowing
      the user to select which label to use.
   -  **Row and column headers** will act like cells with multiple test
      runs.

-  Ctrl-left-clicking on a cell will select (or deselect) the cell.
   Multiple cells can be selected and then right-clicking can be used to
   act on all selected cells.

Table view
~~~~~~~~~~

-  This view will display individual test runs as rows within a table.
   The columns and sorting can be customized. It also has the capability
   to group and show counts.
-  Below the filtering area at the top will be a selection widget
   allowing the user to **select and order the columns displayed**.
-  Below the column selection will be a check box to **"Group by these
   columns and show counts"**. When this is selected, results will be
   grouped by all selected columns and each row will show the count of
   test runs within that group.
-  Clicking on a column header will **sort** the table on that column.
-  Left-clicking on a row will bring the user to the test details tab.
   Right-clicking on a row will bring up a menu allowing the user to go
   to test details or to apply/remove labels.
-  Left-clicking on a grouped row will drilldown to an ungrouped table
   view. Right-clicking will bring up a menu allowing drilldown or
   apply/remove labels.
-  **Job triage** view is a particular table view. It is a grouped table
   view, with columns for job tag, test name, and failure reason. It is
   sorted by these columns in this order, and finally by counts
   descending. This view is particularly useful for triaging failures
   among many test runs and is therefore accessible via shortcuts from
   spreadsheet view.

Plotting view
~~~~~~~~~~~~~

-  Detailed requirements for the plotting view have yet to be
   determined.

Test details
~~~~~~~~~~~~

-  This view will display detailed information for a single test run.
   All of the fields for a test will be displayed, including all hosts
   on which a test ran and their attributes and all test and iteration
   keyvals. Key **log files** will also be readily accessible in
   expandable boxes, including status.log, autoserv.stdout,
   autoserv.stderr, and client.log.\*.

New UI user requirements
------------------------

Use cases
~~~~~~~~~

-  **Job tracking** - viewing a spreadsheet of tests vs machines for a
   given job, with cells showing status of each test on each machine
   (queued, running, passed, failed, etc.). Tests can be sorted in the
   order in which they ran. Results logs are easily accessible. *This is
   mostly available in the old interface. The addition of queued/running
   tests will be the biggest addition. Sorting tests in running order is
   not as simple as it seems (control files aren't guaranteed to be
   deterministic, for example). We have ideas about how to solve that
   but we've deferred it for now.*

-  **Job triage** - viewing a summary of failure reasons for a job. The
   view should display a list of unique failure reasons for each test
   (including job failures) with information on the frequency of each
   failure reason. It should be easy to view the list of machines that
   failed for each reason with links to detailed log files. *See "job
   triage" feature.*

-  **Kernel test status** - viewing a spreadsheet of kernel versions vs
   tests for a set of "official kernel test" jobs, with cells showing
   success rates. User can select which kernel versions to include. It
   should be easy to:

   -  group headers for kernel versions, so that the user can compare
      multiple release candidates within multiple kernel versions
   -  drill down to see machine architecture vs tests for a particular
      kernel version, to assist in triaging architecture-specific
      failures
   -  drill down to see failure reasons for failures of a particular
      test on a particular kernel. As with job triage, this should make
      it easy to drill down to machine lists for each failure reason.
      *Test labels solve the "official kernel tests" problem. Filter
      widgets will ease selection of included kernels. Grouping headers
      by kernel version will***not***be supported for now (this is not
      to be confused with composite headers, which combines two
      different fields). Different drill downs are supported via context
      menus.*

-  **Test series** - user has a pool of machines and runs a test on all
   machines. Machines that fail are triaged and the tests is rerun on
   them, and so on until all machines pass. User should be able to view
   status of last run test within the series for each machine. Triage of
   failed machines should be easy, as in **Job triage**. Additionally,
   user can see state of non-passed machines - failed awaiting triage,
   triaged awaiting re-test, re-test queued/running, etc. *Test labels
   should support this workflow. It will still require a fair bit of
   work on the part of the user, but we felt this was a necessary
   tradeoff in order to avoid putting too much specialized complexity in
   the frontend. Multiple selection should allow fairly powerful label
   usage, which, in combination with saved queries and filter widgets,
   should ease the pain greatly.*

-  **Machine utilization** - viewing a chronological history of all
   tests (and verifies/repairs?) run on a particular machine.
   Test/verify/repair outcome information is displayed, making it easy
   to track down when a certain test started failing or when machine
   verification first failed. Detailed logs are easily accessible.
   *Table view should provide this basic feature. The main lacking
   aspect is inclusion of verify and repair info. This is certainly
   doable but requires further discussion.*

-  **Performance graphs** - plotting performance data vs. kernel version
   for many iterations of a particular test on a particular machine.
   *This, along with the other plotting use cases below, are not being
   addressed now.*

-  **Machine qualification graphs** - plotting a histogram of percentage
   of tests passed on each machine, with bars clickable to view list of
   machines in each bucket.

-  **Utilization graphs** - plotting machine utilization as a percentage
   of time vs. machine, over a given span of time.

-  **Generic keyval graphs** - user selects a set of kernels, a set of
   machines, and a set of tests. In a single graph, all keyvals are
   plotted together (normalized) vs. kernel version. The ordering of
   kernels is completely user-definable. Data points link back to
   results logs.

-  **Kernel benchmark comparisons** - plotting a set of benchmark values
   for a pair of kernels together, to compare the two versions.

-  **Job set comparisons** - plotting a set of benchmark values for two
   sets of jobs together.

Specific feature requests
~~~~~~~~~~~~~~~~~~~~~~~~~

-  Clicking on a kernel brings up a tests vs. status spreadsheet
   filtered for that particular kernel *(possible with drilldown
   options)* *This is a easy shortcut for bringing up a particular
   report.*
-  Reason values displayed in table or one click away *(job triage
   view)* *When triaging a job or jobs with many failures, there needs
   to be a easy way to view a summary of the reasons for failures (from
   the DB "reason" field). Similar reasons should be grouped together
   and it should be easy to see which hosts failed with which reasons.*
-  Include tests that are queued or running in TKO display *(included)*
   *Right now TKO only shows tests that have completed. It should also
   display queued and running tests so the user can get a full picture
   of a job from a single report.*
-  Preserve and display query history *(included as browser history)*
   *The UI should present a list of the last few (or many) spreadsheet
   queries executed, including drilldown history. The user should be
   able to click to go back to a previous query.*
-  Filtering on a list of kernels/jobs to match *(filter widgets)* *The
   user should be able to easily specify a list of kernels and filter
   down to tests run on any of those kernels. Likewise for filtering to
   a list of jobs.*
-  Kernels must sort in chronological order *(not addressed; this is a
   very particular request which we may address with specialized code)*
   *Most fields simply sort alphanumerically, but kernels must sort
   specially so that they come out in chronological order.*
-  Clicking on a kernel brings up a list of failed machines *(context
   menus)* *This is another easy shortcut for bringing up a particular
   report.*
-  Ability to have more than one grouping field for rows or columns (aka
   "composite headers" or "multiple headers") *(included)* *For example,
   the user might specify two fields for row grouping and the resulting
   spreadsheet would have a row for each combination of values from the
   two fields.*
-  Grouping on custom expressions *(not included; potential future
   addition)* *Instead of simply specifying a field to group on, the
   user could specify a custom SQL-like expression.*
-  More powerful filtering by machine labels *(should be possible with
   appropriate usage of machine labels)* *The user should be able to
   filter on machine types both very specifically (i.e. Intel Pentium D
   1GB RAM) and very generally (i.e. all Intel).*
-  Easy way to keep track of where the user is in a large table (when
   row and column headers are no longer visible) *(floating headers)*
   *When browsing a large table, after scrolling to the right and down,
   the row and column headers are no longer visible and the user may
   have no way to know what values a particular cell corresponds to.*
-  Machine-centric view showing utilization of a particular machine over
   time *(see use case; graphical timeline not included)* *This view
   would show a list of things that have been run on the machine in
   chronological order, so the user could get some idea of how the
   machine's been utilized. The ability to view percentage of time in
   use would be good. A graphical timeline sort of view would also be
   good.*
-  CSV data export *(included)* *The user should always be able to
   download the currently displayed data in CSV format.*
-  Invalidation of jobs *(solved with machine labels)* *The user should
   be able to mark jobs (perhaps even individual tests) as invalid and
   have them excluded from TKO reporting.*
-  Powerful and flexible filtering *(included)* *Selections can be
   specified by choosing from a list, by regexp matching or by entering
   raw SQL expressions*
-  Automatic bug filing *(not included)* *When triaging failures, the
   user can click a button to create a new bug in a bugtracking system
   and have job and failure information automatically bundled up and
   attached to the bug.*
-  Filtering on keyvals *(included)* *Users should be able to filter on
   any keyval when filtering results*
