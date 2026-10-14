Settings, errors and the low-level layer
========================================

Settings
--------

.. autofunction:: undata.configure
.. autofunction:: undata.clear_cache

Errors
------

Every error undata raises is an :class:`undata.UNDataError`, with a message that says what
to do next.

.. autoexception:: undata.UNDataError
.. autoexception:: undata.PlaceNotFoundError
.. autoexception:: undata.AmbiguousPlaceError
.. autoexception:: undata.IndicatorNotFoundError
.. autoexception:: undata.AmbiguousIndicatorError
.. autoexception:: undata.ConnectionFailedError
.. autoexception:: undata.APIError
.. autoexception:: undata.BlockedRequestError

Warnings
--------

Data problems are warnings, so the table still comes back. Turn them into errors with
``warnings.simplefilter("error", un.UNDataWarning)``, or silence one kind with
``warnings.simplefilter("ignore", un.MixedYearsWarning)``.

.. autoexception:: undata.UNDataWarning
.. autoexception:: undata.MissingDataWarning
.. autoexception:: undata.MixedYearsWarning
.. autoexception:: undata.StaleDataWarning
.. autoexception:: undata.CoverageWarning
.. autoexception:: undata.PlaceGuessedWarning

Checking data.un.org's search box
---------------------------------

.. autofunction:: undata.ask
.. autoclass:: undata.Answer

The low-level layer
-------------------

For developers: the network client and the identifier grammar the friendly functions
are built on.

.. autoclass:: undata.Transport
   :members: get, post, close
.. autodata:: undata.DEFAULT_BASE_URL
   :annotation:
.. autofunction:: undata.parse_dcid
.. autofunction:: undata.build_dcid
.. autofunction:: undata.describe_dcid
.. autofunction:: undata.child_countries_of
