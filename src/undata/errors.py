"""Exceptions raised by undata.

Every error derives from :class:`UNDataError`, so ``except undata.UNDataError`` is
always enough. The messages are long on purpose: each one says what happened and
what to do next, because the platform's own responses usually do neither.
"""

from __future__ import annotations

__all__ = [
    "APIError",
    "BlockedRequestError",
    "ConnectionFailedError",
    "UNDataError",
]


class UNDataError(Exception):
    """Base class for every error this package raises."""


class ConnectionFailedError(UNDataError):
    """The request never reached the API, or no response arrived in time."""

    def __init__(self, message: str, *, url: str) -> None:
        super().__init__(message)
        self.url = url


class APIError(UNDataError):
    """The API answered with an HTTP error status.

    Attributes:
        status: The HTTP status code.
        url: The full request URL, query string included.
        body: The first 500 characters of the response body.
    """

    def __init__(self, message: str, *, status: int, url: str, body: str) -> None:
        super().__init__(message)
        self.status = status
        self.url = url
        self.body = body

    def __str__(self) -> str:
        return f"{self.args[0]} (HTTP {self.status} from {self.url})"


class BlockedRequestError(APIError):
    """The deployment's firewall refused the request before the API saw it.

    data.un.org needs no API key, so a 403 is never an authentication problem. Two
    request shapes are known to trigger it: a POST body containing a line break, and
    a POST body containing a ``"select"`` key. undata avoids both; seeing this error
    means the firewall's rules have changed, and an issue would be very welcome.
    """
