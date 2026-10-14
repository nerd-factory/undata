Charts
======

``pip install "undata[charts]"`` (matplotlib, and seaborn for :func:`undata.style`);
``pip install "undata[interactive]"`` for Plotly charts.

:func:`undata.chart` reads the table and picks the chart that fits it:

.. list-table::
   :header-rows: 1

   * - Table
     - Chart (``kind=``)
   * - latest values, totals
     - ranked bars (``"bar"``); add ``benchmarks=["World"]`` for reference lines
   * - values over years, up to six countries
     - lines with direct labels (``"line"``)
   * - values over years, more countries
     - small multiples (``"facets"``)
   * - :func:`undata.change`, :func:`undata.trend`, :func:`undata.benchmark`
     - before-and-after dot plot (``"dumbbell"``) or ``"slope"``
   * - :func:`undata.compare` with two indicators
     - scatter (``"scatter"``)
   * - :func:`undata.progress`
     - status chart: baseline, latest and 2030 projection (``"progress"``)
   * - :func:`undata.gap`
     - two-group dot plot with ratios (``"gap"``)
   * - :func:`undata.profile`
     - one row per indicator beside region and world (``"profile"``)
   * - :func:`undata.availability`
     - year-of-latest-value heatmap (``"heatmap"``)
   * - any latest-value table of countries
     - tile map, one equal square per country, no borders (``kind="map"``)

Every chart carries its title, unit and source line, labels its marks, and uses palettes
checked for colour blindness. Save as PNG (300 dpi), SVG or PDF (text stays editable).

.. autofunction:: undata.chart
.. autofunction:: undata.style
.. autofunction:: undata.palette
