======================
Autotest Reporting API
======================

The Autotest Reporting API allows you to embed TKO spreadsheets, tables
and graphs into your own HTML pages. This can be used to create
powerful, customizable dashboards based on Autotest results.

**Currently, only graphs are supported. Spreadsheets and tables are
coming soon.**

Setup
~~~~~

In order to use the Autotest Reporting API, your HTML page needs to load
the Autotest Reporting API Javascript library and then call it to create
widgets. Here's a simple skeleton:

::

    <!DOCTYPE html>
    <head>
      <script type="text/javascript" src="http://your-autotest-server/embedded-tko/autotest.EmbeddedTkoClient.nocache.js">
      <script type="text/javascript">
        function initialize() {
          Autotest.initialize("http://your-autotest-server");

          // code to setup widgets goes here.  for example:
          var plot = Autotest.createMetricsPlot(document.getElementById("plot_canvas"));
          plot.refresh(...); // see below
        }
      </script>
    </head>

    <body onload="initialize()">
      <!-- document outline goes here.  for example: -->
      <div id="plot_canvas"></div>
    </body>

The first script tag loads the Autotest Reporting API library. The
``initialize()`` function then calls ``Autotest.initialize()``, which
tells the library where to find the Autotest server running the TKO web
interface. Finally, it can proceed to call ``Autotest.create*`` methods
to create widgets. All ``Autotest.create*`` methods accept a DOM Element
to which they will attach themselves.

Graphing
~~~~~~~~

You can create a :doc:`MetricsPlot <../frontend/Web/MetricsPlot>` widget using
``Autotest.createMetricsPlot(parentElement)``. Metrics plot widgets have
one method, ``refresh(parameters)``. This interface will be changing
soon so it won't be documented in detail; please see the example in
``frontend/client/src/autotest/public/EmbeddedTkoClientTest`` or
ask showard if you would like to use it and have questions.

