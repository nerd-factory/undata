Analyses
========

The analyses UN reports run most often, one function each. Every result works with
:func:`undata.describe` (which writes the finding), :func:`undata.chart` (which draws the
chart made for it), :func:`undata.save` and :func:`undata.ai_pack`.

Progress towards a target
-------------------------

:func:`undata.progress` follows the UN Statistics Division's *Technical Note for Progress
Assessment*, the method behind the SDG Report's progress charts:

1. Take each country's value at the baseline (2015, or the first year after with data)
   and its latest value, and their compound annual growth rate.
2. With a target, project the latest value to the target year at that rate, and divide
   the projected change by the change the target needs. A ratio of 1 means the target
   is reached on time.
3. Without a target, score the growth rate itself, against fixed thresholds.
4. Place each country in one of the SDG Report's categories, with a score from 0 to 5:

.. list-table::
   :header-rows: 1

   * - Category
     - With a target (ratio)
     - Without a target (annual growth)
   * - On track or target met
     - 0.95 or more
     - 2% or more
   * - Moderate progress, but acceleration needed
     - 0.50 to 0.95
     - 1.25% to 2%
   * - Marginal progress, and significant acceleration needed
     - 0.10 to 0.50
     - 0.5% to 1.25%
   * - Stagnation
     - 0 to 0.10
     - 0 to 0.5%
   * - Regression
     - below 0
     - below 0

When lower is better (mortality, poverty), the growth thresholds are mirrored. A country
that already met the target at the baseline is on track while it still meets it.

.. autofunction:: undata.progress
.. autodata:: undata.STATUSES
   :annotation:

Other analyses
--------------

.. autofunction:: undata.profile
.. autofunction:: undata.gap
.. autofunction:: undata.trend
.. autofunction:: undata.benchmark
.. autofunction:: undata.availability
