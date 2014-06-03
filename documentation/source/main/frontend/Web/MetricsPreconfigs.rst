==================
Metrics Preconfigs
==================

**Metrics preconfigs** should be put in
``<autotest_dir>/new_tko/tko/preconfigs/metrics/``

The parameters are:

-  **plot**: Line or Bar
-  **xAxis**: Database column name for the **X-axis values** control.
   See :doc:`GraphingDatabaseFields <../frontend/Web/GraphingFilters>`.
-  **globalFilter[i][db]**: Database column name for the i\ :sup:`th`\ 
   global filter (start at 0). See
   :doc:`GraphingDatabaseFields <../frontend/Web/GraphingFilters>`.
-  **globalFilter[i][condition]**: Condition field for the
   i\ :sup:`th`\  global filter (start at 0).
-  **globalFilter\_all**: This controls if you have "all of" or "any of"
   selected as the filter combination operation for the global filters.
   Set to ``true`` for "all of", and ``false`` for "any of".
-  **name[j]**: The name of the j\ :sup:`th`\  series.
-  **values[j]**: The database column name that should be plotted on the
   y-axis for the j\ :sup:`th`\  series. See
   :doc:`GraphingDatabaseFields <../frontend/Web/GraphingFilters>`.
-  **aggregation[j]**: The aggregation to be applied to the data of the
   j\ :sup:`th`\  series. Available aggregations are:

   -  AVG
   -  COUNT (DISTINCT)
   -  MIN
   -  MAX

-  **errorBars[j]**: Sets if the error bars should be shown for the
   j\ :sup:`th`\  series, if the aggregation is AVG. Set to ``true`` to
   show error bars, ``false`` to keep them hidden.
-  **seriesFilters[j][k][db]**: Database column name for the
   k\ :sup:`th`\  filter of the j\ :sup:`th`\  series. See
   :doc:`GraphingDatabaseFields <../frontend/Web/GraphingFilters>`.
-  **seriesFilters[j][k][condition]**: Condition field for the
   k\ :sup:`th`\  filter of the j\ :sup:`th`\  series.
-  **seriesFilters[j]\_all**: This controls if you have "all of" or "any
   of" selected as the filter combination operation for the filters on
   the j\ :sup:`th`\  series. Set to ``true`` for "all of", and
   ``false`` for "any of".

Example:

::

    plot: Line
    xAxis: kernel
    globalFilter[0][db]: hostname
    globalFilter[0][condition]: = 'my_test_host'
    globalFilter_all: true
    name[0]: dbench (throughput)
    values[0]: iteration_value
    aggregation[0]: AVG
    errorBars[0]: true
    seriesFilters[0][0][db]: iteration_key
    seriesFilters[0][0][condition]: = 'throughput'
    seriesFilters[0][1][db]: test_name
    seriesFilters[0][1][condition]: = 'dbench'
    seriesFilters[0]_all: true
    name[1]: unixbench (score)
    values[1]: iteration_value
    aggregation[1]: AVG
    errorBars[1]: true
    seriesFilters[1][0][db]: iteration_key
    seriesFilters[1][0][condition]: = 'score'
    seriesFilters[1][1][db]: test_name
    seriesFilters[1][1][condition]: = 'unixbench'
    seriesFilters[1]_all: true

