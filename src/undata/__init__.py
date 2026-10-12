"""undata: a Python client for the UN System Data Commons.

Unofficial, and part of Nerd Lab (https://github.com/nerd-factory). Not affiliated
with or endorsed by the United Nations.

This is a pre-alpha release. What is here today is the foundation: a transport that
avoids the deployment's known firewall traps, a thin wrapper per API route, and the
dcid grammar. The public data, place and search modules come next; see PLAN.md.
"""

from ._http import DEFAULT_BASE_URL, Transport
from ._version import __version__
from .dcid import build_dcid, child_countries_of, describe_dcid, parse_dcid
from .errors import APIError, BlockedRequestError, ConnectionFailedError, UNDataError

__all__ = [
    "DEFAULT_BASE_URL",
    "APIError",
    "BlockedRequestError",
    "ConnectionFailedError",
    "Transport",
    "UNDataError",
    "__version__",
    "build_dcid",
    "child_countries_of",
    "describe_dcid",
    "parse_dcid",
]
