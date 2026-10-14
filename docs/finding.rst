Finding indicators
==================

Start here when you know what you want to measure but not the indicator's id.

.. autofunction:: undata.search
.. autofunction:: undata.about
.. autoclass:: undata.IndicatorInfo
.. autofunction:: undata.breakdowns

The SDG framework
-----------------

Walk from a goal down to the series you can fetch: ``goals()``, then ``targets(16)``,
then ``indicators("16.1")``, then ``series("16.1.2")``.

.. autofunction:: undata.sdg.goals
.. autofunction:: undata.sdg.targets
.. autofunction:: undata.sdg.indicators
.. autofunction:: undata.sdg.series
