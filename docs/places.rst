Countries, regions and groups
=============================

undata ships the UN Statistics Division's M49 standard: 248 countries and areas with
their official names, M49 regions and sub-regions, and the current UN lists of least
developed countries (LDCs), landlocked developing countries (LLDCs) and small island
developing States (SIDS). Places the platform holds outside M49 are in no list, region
or group, and can be reached only by platform code (such as ``country/XKS``).

.. autofunction:: undata.countries
.. autofunction:: undata.regions

Resolving names yourself
------------------------

.. autofunction:: undata.places.resolve
.. autofunction:: undata.places.expand
.. autofunction:: undata.places.m49
.. autoclass:: undata.places.Place
.. autoclass:: undata.places.Country
