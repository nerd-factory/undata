"""undata: UN data in Python, without the guessing.

A friendly client for the UN System Data Commons (data.un.org): statistics from 26
UN System entities, no API key needed. Unofficial, and part of Nerd Lab
(https://github.com/nerd-factory). Not affiliated with or endorsed by the United
Nations.

Start here::

    import undata as un

    un.search("maternal mortality")            # find an indicator
    un.about("undata/sdg/SH_STA_MORT.SEX--F")   # what it is and how much data exists
    table = un.get("undata/sdg/SH_STA_MORT.SEX--F", ["Bangladesh", "Nepal"])
    un.latest("undata/sdg/EG_ACS_ELEC", "Western Africa")
    un.sdg.series("16.1.2")                     # from an SDG indicator to its data
    un.save(table, "maternal-mortality.xlsx")   # data plus a sheet of citations

Every function has a docstring with an example: ``help(un.get)``.
"""

import warnings

from . import places, sdg
from ._http import DEFAULT_BASE_URL, Transport
from ._session import configure
from ._version import __version__
from .ask import Answer, ask
from .data import get, latest
from .dcid import build_dcid, child_countries_of, describe_dcid, parse_dcid
from .errors import (
    AmbiguousPlaceError,
    APIError,
    BlockedRequestError,
    ConnectionFailedError,
    IndicatorNotFoundError,
    MissingDataWarning,
    MixedYearsWarning,
    PlaceGuessedWarning,
    PlaceNotFoundError,
    UNDataError,
    UNDataWarning,
)
from .export import cite, save
from .indicators import IndicatorInfo, about, search
from .places import Place, countries, regions

# Each warning is about the table just returned, so show it every time rather than
# only the first time Python sees it.
warnings.filterwarnings("always", category=UNDataWarning)

__all__ = [
    "DEFAULT_BASE_URL",
    "APIError",
    "AmbiguousPlaceError",
    "Answer",
    "BlockedRequestError",
    "ConnectionFailedError",
    "IndicatorInfo",
    "IndicatorNotFoundError",
    "MissingDataWarning",
    "MixedYearsWarning",
    "Place",
    "PlaceGuessedWarning",
    "PlaceNotFoundError",
    "Transport",
    "UNDataError",
    "UNDataWarning",
    "__version__",
    "about",
    "ask",
    "build_dcid",
    "child_countries_of",
    "cite",
    "configure",
    "countries",
    "describe_dcid",
    "get",
    "latest",
    "parse_dcid",
    "places",
    "regions",
    "save",
    "sdg",
    "search",
]
