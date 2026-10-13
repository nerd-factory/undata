"""Getting numbers: :func:`get` for every year, :func:`latest` for the newest value.

Both return a plain pandas table with one row per country, indicator and year, and
the same columns every time::

    country  iso3  year  value  unit  indicator_name  indicator  source  source_url

Countries with no data are left out of the table and named in a
:class:`~undata.MissingDataWarning`. They are never filled in with zero.
"""

from __future__ import annotations

import warnings
from collections.abc import Iterable, Iterator, Sequence
from datetime import date as _date
from typing import Any, Final

import pandas as pd

from . import _endpoints as api
from . import _session
from .errors import MissingDataWarning, MixedYearsWarning
from .indicators import check, names, source_label
from .places import Place, expand

__all__ = ["get", "latest"]

COLUMNS: Final = [
    "country",
    "iso3",
    "year",
    "value",
    "unit",
    "indicator_name",
    "indicator",
    "source",
    "source_url",
]

#: Places per request. Keeps GET query strings well under common URL limits.
_CHUNK: Final = 50

#: "Latest" values spanning more years than this trigger a MixedYearsWarning.
MIXED_YEARS_TOLERANCE: Final = 2

Years = int | tuple[int, int] | range | Sequence[int] | None


def _chunks(places: list[Place]) -> Iterator[list[Place]]:
    for start in range(0, len(places), _CHUNK):
        yield places[start : start + _CHUNK]


def _year_filter(years: Years) -> set[int] | None:
    if years is None:
        return None
    if isinstance(years, int):
        return {years}
    if isinstance(years, tuple) and len(years) == 2:  # noqa: PLR2004 — (first, last)
        first, last = years
        if first > last:
            raise ValueError(
                f"years=({first}, {last}) runs backwards. Write the earlier year first."
            )
        return set(range(first, last + 1))
    return set(years)


def _year(date: str) -> int | None:
    head = date[:4]
    return int(head) if head.isdigit() else None


def _unit(facet: dict[str, Any]) -> str | None:
    """The unit's display name. Some responses give only its graph id."""
    if facet.get("unitDisplayName"):
        return str(facet["unitDisplayName"])
    unit = facet.get("unit")
    if not unit:
        return None
    return names([unit]).get(unit, unit) if "/" in unit else str(unit)


def _row(
    place: Place,
    indicator: str,
    indicator_name: str,
    observation: dict[str, Any],
    facet: dict[str, Any],
) -> dict[str, Any]:
    return {
        "country": place.name,
        "iso3": place.iso3,
        "year": _year(str(observation.get("date", ""))),
        "value": observation.get("value"),
        "unit": _unit(facet),
        "indicator_name": indicator_name,
        "indicator": indicator,
        "source": source_label(facet["provenanceId"]) if facet.get("provenanceId") else None,
        "source_url": facet.get("provenanceUrl"),
    }


def _frame(rows: list[dict[str, Any]], missing: list[tuple[str, str]]) -> pd.DataFrame:
    frame = pd.DataFrame(rows, columns=COLUMNS)
    frame["year"] = frame["year"].astype("Int64")
    frame["value"] = pd.to_numeric(frame["value"])
    frame = frame.sort_values(["indicator", "country", "year"], ignore_index=True)
    frame.attrs["missing"] = [{"country": c, "indicator_name": n} for c, n in missing]
    frame.attrs["retrieved"] = _date.today().isoformat()
    return frame


def _warn_missing(missing: list[tuple[str, str]], asked: int, stacklevel: int = 3) -> None:
    if not missing:
        return
    by_indicator: dict[str, list[str]] = {}
    for country, indicator_name in missing:
        by_indicator.setdefault(indicator_name, []).append(country)
    lines = []
    for indicator_name, countries in by_indicator.items():
        shown = ", ".join(countries[:8])
        more = f" and {len(countries) - 8} more" if len(countries) > 8 else ""  # noqa: PLR2004
        lines.append(f"  {indicator_name}: {shown}{more}")
    warnings.warn(
        f"No data for {len(missing)} of {asked} country/indicator combinations. They are "
        "left out of the table, not set to zero:\n" + "\n".join(lines) + "\n"
        "The full list is in table.attrs['missing'].",
        MissingDataWarning,
        stacklevel=stacklevel,
    )


def _collect(
    indicator_names: dict[str, str],
    places: list[Place],
    *,
    keep: set[int] | None,
    last_only: bool,
) -> tuple[list[dict[str, Any]], list[tuple[str, str]]]:
    """Fetch series for every indicator and place, and turn them into rows.

    Both get() and latest() use the POST series route. The GET observation route
    would be lighter for latest(), but the firewall refuses any GET whose query
    contains Western Sahara's code, ESH, so a request for "Africa" would fail.
    """
    rows: list[dict[str, Any]] = []
    missing: list[tuple[str, str]] = []
    for chunk in _chunks(places):
        body = api.series(_session.transport(), list(indicator_names), [p.id for p in chunk])
        facets = body.get("facets", {})
        for indicator, name in indicator_names.items():
            by_place = body.get("data", {}).get(indicator, {})
            for place in chunk:
                block = by_place.get(place.id) or {}
                facet = facets.get(block.get("facet", ""), {})
                kept = [
                    obs
                    for obs in block.get("series") or []
                    if keep is None or _year(str(obs.get("date", ""))) in keep
                ]
                if not kept:
                    missing.append((place.name, name))
                    continue
                if last_only:
                    kept = [max(kept, key=lambda obs: str(obs.get("date", "")))]
                rows.extend(_row(place, indicator, name, obs, facet) for obs in kept)
    return rows, missing


def get(
    indicators: str | Sequence[str],
    countries: str | Iterable[str],
    years: Years = None,
) -> pd.DataFrame:
    """Get an indicator's values for some countries, for every year or a range of years.

    Args:
        indicators: One indicator id, or a list. Find ids with :func:`undata.search`.
        countries: Country names, ISO codes or regions, alone or in a list:
            ``"Nepal"``, ``["Bangladesh", "Viet Nam"]``, ``"Southern Asia"``.
        years: Leave out for every year. ``2020`` for one year, ``(2015, 2023)`` for
            an inclusive range, or a list of years.

    Returns:
        A table with one row per country, indicator and year. Countries with no data
        are left out and named in a :class:`~undata.MissingDataWarning`.

    Example:
        >>> import undata as un
        >>> mmr = "undata/sdg/SH_STA_MORT.SEX--F"
        >>> un.get(mmr, ["Bangladesh", "Nepal"], years=(2020, 2023))  # doctest: +SKIP
              country iso3  year       value                          unit  ...
        0  Bangladesh  BGD  2020  151.84625  Count per 100,000 live births  ...
    """
    indicator_names = check(indicators)
    places = expand(countries)
    rows, missing = _collect(indicator_names, places, keep=_year_filter(years), last_only=False)
    _warn_missing(missing, len(places) * len(indicator_names))
    return _frame(rows, missing)


def latest(indicators: str | Sequence[str], countries: str | Iterable[str]) -> pd.DataFrame:
    """Get each country's most recent value for an indicator.

    "Most recent" is per country, so one country's latest value may be from 2023 and
    another's from 2015. The ``year`` column says which, and a
    :class:`~undata.MixedYearsWarning` is shown when the years differ by more than two.

    Args:
        indicators: One indicator id, or a list. Find ids with :func:`undata.search`.
        countries: Country names, ISO codes or regions, alone or in a list.

    Returns:
        A table with one row per country and indicator, in the same columns as
        :func:`get`.

    Example:
        >>> import undata as un
        >>> un.latest("undata/sdg/EG_ACS_ELEC", "Western Africa")  # doctest: +SKIP
    """
    indicator_names = check(indicators)
    places = expand(countries)
    rows, missing = _collect(indicator_names, places, keep=None, last_only=True)
    _warn_missing(missing, len(places) * len(indicator_names))
    frame = _frame(rows, missing)
    for indicator_name, group in frame.groupby("indicator_name"):
        first, last = group["year"].min(), group["year"].max()
        if pd.notna(first) and last - first > MIXED_YEARS_TOLERANCE:
            warnings.warn(
                f"The latest values for {indicator_name} come from different years, "
                f"{first} to {last}. Values from different years are not directly "
                "comparable; the year column shows which is which.",
                MixedYearsWarning,
                stacklevel=2,
            )
    return frame
