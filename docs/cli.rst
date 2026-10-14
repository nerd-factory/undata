Command line
============

Everything in the package also works from a terminal, for scripts and quick checks:

.. code-block:: bash

   undata search "maternal mortality"
   undata latest 3.1.1 LDCs --within 10 --to mmr.xlsx
   undata totals 3.1.1 World LDCs --latest

Errors print a plain message and exit with status 1; data warnings print as notes.
The help below is generated from the command itself.

.. include:: _generated/cli.rst
