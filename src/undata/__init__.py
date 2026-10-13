"""undata: UN data in Python, without the guessing.

A friendly client for the UN System Data Commons (data.un.org): statistics from 26
UN System entities, no API key needed. Unofficial, and part of Nerd Lab
(https://github.com/nerd-factory). Not affiliated with or endorsed by the United
Nations.

Start here::

    import undata as un

    un.search("maternal mortality")             # find an indicator
    un.about("3.1.1")                            # what it is, with its SDG metadata link
    table = un.get("3.1.1", ["Bangladesh", "Nepal"], years=(2015, 2023))
    un.latest("undata/sdg/EG_ACS_ELEC", "LDCs", since=2020)
    un.totals("3.1.1", ["World", "Africa", "SIDS"], latest=True)
    un.change("3.1.1", "Southern Asia", 2015, 2023)
    print(un.describe(table))                    # sentences for a report
    un.chart(table)                              # a chart with its source underneath
    un.save(table, "maternal-mortality.xlsx")    # data plus a sheet of citations

Every function has a docstring with an example: ``help(un.get)``.
"""

import warnings

from . import places, sdg
from ._http import DEFAULT_BASE_URL, Transport
from ._session import clear_cache, configure
from ._version import __version__
from .ask import Answer, ask
from .breakdowns import breakdowns
from .chart import chart
from .data import change, compare, get, latest, totals, wide
from .dcid import build_dcid, child_countries_of, describe_dcid, parse_dcid
from .errors import (
    AmbiguousIndicatorError,
    AmbiguousPlaceError,
    APIError,
    BlockedRequestError,
    ConnectionFailedError,
    CoverageWarning,
    IndicatorNotFoundError,
    MissingDataWarning,
    MixedYearsWarning,
    PlaceGuessedWarning,
    PlaceNotFoundError,
    StaleDataWarning,
    UNDataError,
    UNDataWarning,
)
from .export import cite, for_ai, powerquery, save
from .indicators import IndicatorInfo, about, search
from .places import Place, countries, regions
from .summary import describe

# Each warning is about the table just returned, so show it every time rather than
# only the first time Python sees it.
warnings.filterwarnings("always", category=UNDataWarning)

__all__ = [
    "DEFAULT_BASE_URL",
    "APIError",
    "AmbiguousIndicatorError",
    "AmbiguousPlaceError",
    "Answer",
    "BlockedRequestError",
    "ConnectionFailedError",
    "CoverageWarning",
    "IndicatorInfo",
    "IndicatorNotFoundError",
    "MissingDataWarning",
    "MixedYearsWarning",
    "Place",
    "PlaceGuessedWarning",
    "PlaceNotFoundError",
    "StaleDataWarning",
    "Transport",
    "UNDataError",
    "UNDataWarning",
    "__version__",
    "about",
    "ask",
    "breakdowns",
    "build_dcid",
    "change",
    "chart",
    "child_countries_of",
    "cite",
    "clear_cache",
    "compare",
    "configure",
    "countries",
    "describe",
    "describe_dcid",
    "for_ai",
    "get",
    "latest",
    "parse_dcid",
    "places",
    "powerquery",
    "regions",
    "save",
    "sdg",
    "search",
    "totals",
    "wide",
]
