==================================================
Using the Machine Qualification Histogram Frontend
==================================================

The **Machine qualification histogram frontend** is able to generate a
histogram of test pass rates for a specified set of tests and machines.
The histogram shows bins of configurable size for pass rates between 0
and 100, exclusive, as well as special bins for 0% and 100% pass rates.
There is also an "N/A" bin, which shows the machines that did not run
any of the tests that you specified to analyze.

[[MachineQualHistograms/machine_qual_interface.png]]

Using the Interface
-------------------

Interface Options
~~~~~~~~~~~~~~~~~

-  **Graph Type**: Set to "Machine Qualification Histogram" to show this
   interface.
-  **Preconfigured**: Select a preconfigured graphing query. Use this to
   automatically populate the fields in the interface to a preconfigured
   example. You may then submit the query for plotting as is, or edit
   the fields to modify the query. See
   :doc:`Graphing Pre Configs <../frontend/Web/GraphingPreconfigs>` to more information
   about preconfigured queries.
-  **Global filters**: Set the filters on the machines you would like to
   see. Any machine that satisfies the filter will be plotted in the
   histogram in some way. See `GraphingFilters <GraphingFilters>`_
   for more information on setting a filter.
-  **Test set filters**: Set the filters on the tests that you want to
   analyze. The pass rates for what you enter in this filter will be
   plotted on the histogram. If a machine satisfies the **Global
   filters** above but has not run any tests that satisfy the **Test set
   filters**, it will appear in the "N/A" bin. See
   `GraphingFilters <GraphingFilters>`_ for more information on
   setting a filter.
-  **Interval**: Configure the size of each bin. For example, an
   interval of 5 means that the bins should be 0%-5%, 5%-10%, etc.

Interacting with the Graph
~~~~~~~~~~~~~~~~~~~~~~~~~~

The four main actions you can do on the graph are:

-  **Hover**: Hovering the cursor over a bar shows a tooltip displaying
   the boundaries of the bin and the number of machines in that bin.
-  **Click**: Clicking on a bar jumps to the **Table view**,
   automatically configured to show the specific machines and pass rates
   in that bin.
-  **Embed**: Clicking the [Link to this Graph] link at the bottom-right
   of the generated plot displays an HTML snippet you can paste into a
   webpage to embed the graph. The embedded graph updates with live data
   at a specified refresh rate (as the max\_age URL parameter, which is
   in minutes), and show an indication of the last time it was updated.
   Clicking on the embedded graph links to the **Machine qualification
   histogram frontend**, automatically populated with the query that
   will generate the graph.
-  **Save**: The graph is delivered as a PNG image, so you can simply
   right-click it and save it if you want a snapshot of the graph at a
   certain point in time.
