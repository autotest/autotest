================================
Machine Qualification Preconfigs
================================

**Machine qualification preconfigs** should be put in
``<autotest_dir>/new_tko/tko/preconfigs/qual/``

The parameters are:

-  **globalFilter[i][db]**: Database column name for the i\ :sup:`th`\ 
   global filter (start at 0). See
   :doc:`GraphingDatabaseFields <../frontend/Web/GraphingFilters>`.
-  **globalFilter[i][condition]**: Condition field for the
   i\ :sup:`th`\  global filter (start at 0).
-  **globalFilter\_all**: This controls if you have "all of" or "any of"
   selected as the filter combination operation for the global filters.
   Set to ``true`` for "all of", and ``false`` for "any of".
-  **testFilter[j][db]**: Database column name for the j\ :sup:`th`\ 
   test set filter (start at 0). See
   :doc:`GraphingDatabaseFields <../frontend/Web/GraphingFilters>`.
-  **testFilter[j][condition]**: Condition field for the j\ :sup:`th`\ 
   test set filter (start at 0).
-  **testFilter\_all**: This controls if you have "all of" or "any of"
   selected as the filter combination operation for the test set
   filters. Set to ``true`` for "all of", and ``false`` for "any of".
-  **interval**: Sizes of the bins in the histogram.

Example:

::

    globalFilter[0][db]: hostname
    globalFilter[0][condition]: LIKE 'my_host_names%'
    globalFilter[1][db]: hostname
    globalFilter[1][condition]: LIKE 'my_other_host_names%'
    globalFilter_all: false
    testFilter[0][db]: test_name
    testFilter[0][condition]: = 'my_test_name'
    testFilter_all: true
    interval: 10

