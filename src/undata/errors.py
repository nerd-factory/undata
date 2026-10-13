"""Errors and warnings raised by undata.

Every error derives from :class:`UNDataError`, so ``except undata.UNDataError`` is
always enough. The messages are long on purpose: each one says what happened and
what to do next, in words that do not assume a data background.

Warnings derive from :class:`UNDataWarning`. They are shown every time, not just
the first time, because each one is about the table you just asked for. Silence one
kind with ``warnings.filterwarnings("ignore", category=undata.MissingDataWarning)``.
"""

from __future__ import annotations

from collections.abc import Sequence

__all__ = [
    "APIError",
    "AmbiguousPlaceError",
    "BlockedRequestError",
    "ConnectionFailedError",
    "IndicatorNotFoundError",
    "MissingDataWarning",
    "MixedYearsWarning",
    "PlaceGuessedWarning",
    "PlaceNotFoundError",
    "UNDataError",
    "UNDataWarning",
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


def _did_you_mean(suggestions: Sequence[str]) -> str:
    if not suggestions:
        return ""
    return " Did you mean: " + ", ".join(repr(s) for s in suggestions) + "?"


class PlaceNotFoundError(UNDataError, LookupError):
    """A country or region name was not recognised.

    undata never substitutes a different place for one it does not recognise.

    Attributes:
        name: What was asked for.
        suggestions: Close matches, best first. May be empty.
    """

    def __init__(self, name: str, suggestions: Sequence[str] = ()) -> None:
        self.name = name
        self.suggestions = list(suggestions)
        super().__init__(
            f"{name!r} is not a country or region undata recognises."
            f"{_did_you_mean(self.suggestions)} "
            "Run un.countries() or un.regions() to see every name it knows."
        )


class AmbiguousPlaceError(PlaceNotFoundError):
    """A name matches more than one country, so undata will not pick one."""

    def __init__(self, name: str, suggestions: Sequence[str]) -> None:
        self.name = name
        self.suggestions = list(suggestions)
        UNDataError.__init__(
            self,
            f"{name!r} could mean more than one country: "
            + ", ".join(repr(s) for s in self.suggestions)
            + ". Use the full name or the three-letter code.",
        )


class IndicatorNotFoundError(UNDataError, LookupError):
    """An indicator id was not recognised, or a phrase was given instead of an id.

    Attributes:
        name: What was asked for.
        suggestions: Indicator ids from a search for it, best first. May be empty.
    """

    def __init__(self, name: str, suggestions: Sequence[str] = (), *, phrase: bool) -> None:
        self.name = name
        self.suggestions = list(suggestions)
        if phrase:
            what = f"{name!r} looks like a description, not an indicator id."
        else:
            what = f"No indicator has the id {name!r}."
        super().__init__(
            f"{what}{_did_you_mean(self.suggestions)} "
            f"Run un.search({name!r}) to see matching indicators with their names."
        )


class UNDataWarning(UserWarning):
    """Base class for every warning this package raises."""


class MissingDataWarning(UNDataWarning):
    """Some of the countries you asked for have no data for an indicator.

    Missing data is left out of the table, never filled with zero.
    """


class MixedYearsWarning(UNDataWarning):
    """The "latest" values come from different years, so compare them with care."""


class PlaceGuessedWarning(UNDataWarning):
    """data.un.org's search chose a place your question did not name."""
