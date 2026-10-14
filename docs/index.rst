undata reference
================

undata is a Python package for the `UN System Data Commons <https://data.un.org>`_: type a
country's name, get a table of UN statistics with the unit, year and source on every row.
This is the reference for every function. For worked examples with real output, see the
`use cases <https://nerd-factory.github.io/undata/>`_.

.. code-block:: bash

   pip install undata                 # tables and Excel
   pip install "undata[charts]"       # + charts
   pip install "undata[all]"          # + interactive charts and the AI connector

.. code-block:: python

   import undata as un

   table = un.latest("3.1.1", "LDCs", within=10)   # each LDC's latest maternal mortality ratio
   print(un.describe(table))                        # a sentence for the report
   un.save(table, "maternal-mortality.xlsx")        # with sources on their own sheet

Conventions used everywhere
---------------------------

**Places.** Wherever a function asks for countries you can pass a name the way you would
write it (``"Viet Nam"``, ``"Vietnam"``, ``"VNM"``), a list of names, an M49 region
(``"Southern Asia"``, ``"Africa"``), or a UN group (``"LDCs"``, ``"LLDCs"``, ``"SIDS"``).
Regions and groups expand to their member countries. Tables use the UN's official names.

**Indicators.** An indicator id from :func:`undata.search` (such as
``"undata/sdg/SH_STA_MORT.SEX--F"``), or an SDG number (``"3.1.1"``) when one series
reports it. When several do, the error lists them.

**Tables.** Functions return :class:`pandas.DataFrame` objects with one row per value,
and keep their metadata (sources, the years asked for, what was missing) in
``table.attrs``, so :func:`undata.describe`, :func:`undata.cite`, :func:`undata.save` and
:func:`undata.chart` know where the numbers came from.

**Warnings.** Data problems (missing countries, values from different years, old values)
are reported as warnings, never as zeros. See :doc:`config`.

.. toctree::
   :maxdepth: 2
   :caption: Reference

   finding
   places
   data
   analysis
   summaries
   charts
   connector
   cli
   config

.. toctree::
   :caption: Project

   Use cases <https://nerd-factory.github.io/undata/>
   Changelog <https://github.com/nerd-factory/undata/blob/main/CHANGELOG.md>
   Source <https://github.com/nerd-factory/undata>
   PyPI <https://pypi.org/project/undata/>

undata is an unofficial `Nerd Lab <https://github.com/nerd-factory>`_ project, not
affiliated with or endorsed by the United Nations. The data belongs to the agencies that
publish it.
