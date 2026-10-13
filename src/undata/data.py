"""Getting numbers.

* :func:`get` - every year, or a range of years.
* :func:`latest` - each country's newest value.
* :func:`totals` - the official figure for a region or group, as the agency published it.
* :func:`change` - between two years: before, after, and the difference.
* :func:`compare` - two or more indicators side by side, with who is missing spelled out.
* :func:`wide` - any of the above as one column per indicator.

All return a plain pandas table, and all but :func:`change`, :func:`compare` and
:func:`wide` have the same columns every time::

    country  iso3  year  value  unit  indicator_name  indicator  source  source_url

Countries with no data are left out of the table and named in a
:class:`~undata.MissingDataWarning`. They are never filled in with zero.
"""

from __future__ import annotations

import warnings
from collections.abc import Iterable, Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor
from datetime import date as _date
from typing import Any, Final

import pandas as pd

from . import _endpoints as api
from . import _session
from ._long import keep
from .breakdowns import slices_by
from .errors import CoverageWarning, MissingDataWarning, MixedYearsWarning, StaleDataWarning
from .indicators import check, names, source_label
from .places import Place, expand, resolve

__all__ = ["change", "compare", "get", "latest", "totals", "wide"]

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

#: Places per request, and how many requests run at once.
_CHUNK: Final = 50
_WORKERS: Final = 4

#: "Latest" values spanning more years than this trigger a MixedYearsWarning.
MIXED_YEARS_TOLERANCE: Final = 2

Years = int | tuple[int, int] | range | Sequence[int] | None


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


def _frame(
    rows: list[dict[str, Any]],
    missing: list[tuple[str, str]],
    columns: Sequence[str] = COLUMNS,
) -> pd.DataFrame:
    frame = pd.DataFrame(rows, columns=list(columns))
    frame["year"] = frame["year"].astype("Int64")
    frame["value"] = pd.to_numeric(frame["value"])
    frame = frame.sort_values(["indicator", "country", "year"], ignore_index=True)
    frame.attrs["missing"] = [{"country": c, "indicator_name": n} for c, n in missing]
    frame.attrs["retrieved"] = _date.today().isoformat()
    return frame


def _shorten(items: Sequence[str], limit: int = 8) -> str:
    shown = ", ".join(items[:limit])
    return f"{shown} and {len(items) - limit} more" if len(items) > limit else shown


def _warn_missing(missing: list[tuple[str, str]], asked: int, stacklevel: int = 3) -> None:
    if not missing:
        return
    by_indicator: dict[str, list[str]] = {}
    for country, indicator_name in missing:
        by_indicator.setdefault(indicator_name, []).append(country)
    lines = [f"  {name}: {_shorten(countries)}" for name, countries in by_indicator.items()]
    warnings.warn(
        f"No data for {len(missing)} of {asked} country/indicator combinations. They are "
        "left out of the table, not set to zero:\n" + "\n".join(lines) + "\n"
        "The full list is in table.attrs['missing'].",
        MissingDataWarning,
        stacklevel=stacklevel,
    )


def _warn_mixed_years(frame: pd.DataFrame, stacklevel: int = 3) -> None:
    for indicator_name, group in frame.groupby("indicator_name"):
        first, last = group["year"].min(), group["year"].max()
        if pd.notna(first) and last - first > MIXED_YEARS_TOLERANCE:
            warnings.warn(
                f"The latest values for {indicator_name} come from different years, "
                f"{first} to {last}. Values from different years are not directly "
                "comparable; the year column shows which is which. Pass within=N to keep "
                "only values from the past N years.",
                MixedYearsWarning,
                stacklevel=stacklevel,
            )


def _fetch(indicators: list[str], places: list[Place]) -> list[tuple[list[Place], dict[str, Any]]]:
    """Fetch series in chunks of places, several requests at once.

    Fetching runs on worker threads; everything that touches the session cache
    happens afterwards, on the calling thread.
    """
    transport = _session.transport()
    chunks = [places[i : i + _CHUNK] for i in range(0, len(places), _CHUNK)]

    def one(chunk: list[Place]) -> dict[str, Any]:
        result: dict[str, Any] = api.series(transport, indicators, [p.id for p in chunk])
        return result

    if len(chunks) == 1:
        return [(chunks[0], one(chunks[0]))]
    with ThreadPoolExecutor(max_workers=_WORKERS) as pool:
        return list(zip(chunks, pool.map(one, chunks), strict=True))


def _collect(
    indicator_names: dict[str, str],
    places: list[Place],
    *,
    keep: set[int] | None,
    last_only: bool,
) -> tuple[list[dict[str, Any]], list[tuple[str, str]]]:
    """Fetch series for every indicator and place, and turn them into rows.

    Everything goes through the POST series route. The GET observation route would
    be lighter for latest(), but the firewall refuses any GET whose query contains
    Western Sahara's code, ESH, so a request for "Africa" would fail.
    """
    rows: list[dict[str, Any]] = []
    missing: list[tuple[str, str]] = []
    for chunk, body in _fetch(list(indicator_names), places):
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


def wide(table: pd.DataFrame) -> pd.DataFrame:
    """Turn a table into one column per indicator, one row per country (and year).

    Args:
        table: A table from :func:`get`, :func:`latest` or :func:`totals`.

    Returns:
        The values, with countries down the side and indicator names across the top.
        A table that has several years per country keeps a ``year`` level in the
        index. The original table stays attached, so :func:`undata.cite`
        and :func:`undata.save` still know the sources.

    Example:
        >>> import undata as un
        >>> un.wide(un.latest([electricity, water], "Southern Asia"))  # doctest: +SKIP
    """
    if table.empty:
        result = pd.DataFrame(index=pd.Index([], name="country"))
    else:
        several_years = table.groupby(["country", "indicator"])["year"].nunique().max() > 1
        index = ["country", "year"] if several_years else ["country"]
        result = table.pivot_table(
            index=index, columns="indicator_name", values="value", aggfunc="first"
        )
        result.columns.name = None
    result.attrs = dict(table.attrs)
    return keep(result, table)


# The functions below take a ``wide=True`` argument, which hides the function above.
_to_wide = wide


def get(
    indicators: str | Sequence[str],
    countries: str | Iterable[str],
    years: Years = None,
    *,
    by: str | None = None,
    wide: bool = False,
) -> pd.DataFrame:
    """Get an indicator's values for some countries, for every year or a range of years.

    Args:
        indicators: One indicator id, or a list. An SDG indicator number such as
            ``"3.1.1"`` works too. Find ids with :func:`undata.search`.
        countries: Country names, ISO codes, regions or groups, alone or in a list:
            ``"Nepal"``, ``["Bangladesh", "Viet Nam"]``, ``"Southern Asia"``, ``"LDCs"``.
        years: Leave out for every year. ``2020`` for one year, ``(2015, 2023)`` for
            an inclusive range, or a list of years.
        by: A breakdown, such as ``"sex"`` or ``"age"``. Adds a column with the
            breakdown's values; see :func:`undata.breakdowns` for what exists.
        wide: Return one column per indicator instead of one row per value.

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
    keep = _year_filter(years)
    columns: Sequence[str] = COLUMNS
    if by is not None:
        column = by.strip().lower()
        sliced = {i: slices_by(i, by) for i in indicator_names}
        labels = {s: label for slices in sliced.values() for s, label in slices.items()}
        indicator_names = check(list(labels))
        columns = [*COLUMNS[:6], column, *COLUMNS[6:]]
    rows, missing = _collect(indicator_names, places, keep=keep, last_only=False)
    if by is not None:
        for row in rows:
            row[column] = labels[row["indicator"]]
    _warn_missing(missing, len(places) * len(indicator_names))
    frame = _frame(rows, missing, columns)
    return _to_wide(frame) if wide else frame


def latest(
    indicators: str | Sequence[str],
    countries: str | Iterable[str],
    *,
    within: int | None = None,
    since: int | None = None,
    wide: bool = False,
) -> pd.DataFrame:
    """Get each country's most recent value for an indicator.

    Many series are not published every year for every country, so "most recent"
    is per country: one country's latest value may be from 2023 and another's from
    2015. The ``year`` column says which. To keep only recent enough values, say how
    far back to look: ``within=10`` takes each country's latest value from the past
    ten years, and names the countries whose latest is older.

    Args:
        indicators: One indicator id or SDG indicator number, or a list of them.
        countries: Country names, ISO codes, regions or groups, alone or in a list.
        within: Look back this many years from this year, so ``within=5`` in 2026
            keeps values from 2021 on. Older values are left out and named in a
            :class:`~undata.StaleDataWarning`.
        since: The same, as a year: ``since=2020`` keeps values from 2020 on.
        wide: Return one column per indicator instead of one row per value.

    Returns:
        A table with one row per country and indicator, in the same columns as
        :func:`get`. ``.attrs["window"]`` records the years looked at, and
        :func:`undata.coverage` summarises who has a value, who was too old and who
        has none.

    Example:
        >>> import undata as un
        >>> table = un.latest("3.1.1", "Western Africa", within=5)  # doctest: +SKIP
        >>> un.coverage(table)  # doctest: +SKIP
    """
    if within is not None and since is not None:
        raise ValueError("Pass within= or since=, not both.")
    this_year = _date.today().year
    if within is not None:
        if within < 0:
            raise ValueError("within= counts years back from this one, so it cannot be negative.")
        since = this_year - within
    indicator_names = check(indicators)
    places = expand(countries)
    rows, missing = _collect(indicator_names, places, keep=None, last_only=True)
    _warn_missing(missing, len(places) * len(indicator_names))
    frame = _frame(rows, missing)
    frame.attrs["asked"] = [p.name for p in places]
    frame.attrs["window"] = {"within_years": within, "since": since, "until": this_year}
    frame.attrs["stale"] = []
    if since is not None:
        old = frame["year"] < since
        stale = frame[old]
        frame = frame[~old].reset_index(drop=True)
        frame.attrs["stale"] = stale[["country", "indicator_name", "year"]].to_dict("records")
        if not stale.empty:
            listed = [f"{r.country} ({r.year})" for r in stale.itertuples()]
            span = f" (outside the last {within} years)" if within is not None else ""
            warnings.warn(
                f"Left out {len(stale)} values older than {since}{span}: {_shorten(listed)}. "
                "They are in table.attrs['stale']; un.coverage(table) summarises them.",
                StaleDataWarning,
                stacklevel=2,
            )
    _warn_mixed_years(frame)
    return _to_wide(frame) if wide else frame


def totals(
    indicators: str | Sequence[str],
    places: str | Iterable[str],
    years: Years = None,
    *,
    latest: bool = False,
    wide: bool = False,
) -> pd.DataFrame:
    """Get the official figure for a region or group, as the agency published it.

    :func:`get` treats ``"Africa"`` as every country in Africa. This asks for Africa
    itself: the regional total or average the agency computed with its own method.
    undata never computes one of its own. The ``country`` column holds the region's
    name.

    Args:
        indicators: One indicator id or SDG indicator number, or a list of them.
        places: Regions or groups such as ``"World"``, ``"Africa"``, ``"LDCs"``.
            Countries work too, and give the country's own value.
        years: As for :func:`get`.
        latest: Keep only each place's most recent value.
        wide: Return one column per indicator instead of one row per value.

    Example:
        >>> import undata as un
        >>> un.totals("3.1.1", ["World", "LDCs", "SIDS"], latest=True)  # doctest: +SKIP
    """
    indicator_names = check(indicators)
    asked = [places] if isinstance(places, str) else list(places)
    resolved = list({p.id: p for p in (resolve(name) for name in asked)}.values())
    rows, missing = _collect(indicator_names, resolved, keep=_year_filter(years), last_only=latest)
    _warn_missing(missing, len(resolved) * len(indicator_names))
    frame = _frame(rows, missing)
    return _to_wide(frame) if wide else frame


CHANGE_COLUMNS: Final = [
    "country",
    "iso3",
    "indicator_name",
    "start_year",
    "start_value",
    "end_year",
    "end_value",
    "change",
    "change_pct",
    "unit",
    "indicator",
    "source",
]


def change(
    indicators: str | Sequence[str],
    countries: str | Iterable[str],
    start: int,
    end: int,
) -> pd.DataFrame:
    """Compare two years: the value in each, the difference, and the percentage change.

    Only countries with a value in both years are in the table; the rest are named
    in a :class:`~undata.MissingDataWarning`.

    Args:
        indicators: One indicator id or SDG indicator number, or a list of them.
        countries: Country names, ISO codes, regions or groups.
        start: The earlier year, such as 2015 for the SDG baseline.
        end: The later year.

    Returns:
        One row per country and indicator: ``start_value``, ``end_value``, ``change``
        and ``change_pct``.

    Example:
        >>> import undata as un
        >>> un.change("3.1.1", "Southern Asia", 2015, 2023)  # doctest: +SKIP
    """
    if start >= end:
        raise ValueError(f"start ({start}) must be earlier than end ({end}).")
    indicator_names = check(indicators)
    places = expand(countries)
    rows, _ = _collect(indicator_names, places, keep={start, end}, last_only=False)
    by_key: dict[tuple[str, str], dict[int, dict[str, Any]]] = {}
    for row in rows:
        by_key.setdefault((row["country"], row["indicator"]), {})[row["year"]] = row
    out: list[dict[str, Any]] = []
    missing: list[tuple[str, str]] = []
    for place in places:
        for indicator, name in indicator_names.items():
            pair = by_key.get((place.name, indicator), {})
            if start not in pair or end not in pair:
                missing.append((place.name, name))
                continue
            before, after = pair[start], pair[end]
            delta = after["value"] - before["value"]
            out.append(
                {
                    "country": place.name,
                    "iso3": place.iso3,
                    "indicator_name": name,
                    "start_year": start,
                    "start_value": before["value"],
                    "end_year": end,
                    "end_value": after["value"],
                    "change": delta,
                    "change_pct": delta / before["value"] * 100 if before["value"] else None,
                    "unit": after["unit"],
                    "indicator": indicator,
                    "source": after["source"],
                }
            )
    _warn_missing(missing, len(places) * len(indicator_names))
    frame = pd.DataFrame(out, columns=CHANGE_COLUMNS).sort_values(
        ["indicator", "country"], ignore_index=True
    )
    frame.attrs["missing"] = [{"country": c, "indicator_name": n} for c, n in missing]
    frame.attrs["retrieved"] = _date.today().isoformat()
    return keep(frame, _frame(rows, []))


def compare(
    indicators: Sequence[str] | Mapping[str, str],
    countries: str | Iterable[str],
    *,
    within: int | None = None,
    since: int | None = None,
) -> pd.DataFrame:
    """Put several indicators side by side, each country's latest value of each.

    Before two indicators go on one chart, the question is who has both. A
    :class:`~undata.CoverageWarning` answers it: how many countries have every
    indicator, and which have only some. Countries with none are left out.

    Args:
        indicators: Indicator ids, or a mapping of short labels to ids, such as
            ``{"conflict": "undata/sdg/VC_DTH_TOTR", "homicide": "undata/sdg/VC_IHR_PSRC"}``.
            Labels become the column names; without them, indicator names are used.
        countries: Country names, ISO codes, regions or groups.
        within: As for :func:`latest`: each country's latest value from the past
            this many years.
        since: As for :func:`latest`.

    Returns:
        One row per country with a value column and a year column per indicator.
        ``.attrs["coverage"]`` holds who has what.

    Example:
        >>> import undata as un
        >>> un.compare({"conflict": conflict, "homicide": homicide}, "World")  # doctest: +SKIP
    """
    labelled = dict(indicators) if isinstance(indicators, Mapping) else None
    ids = list(labelled.values()) if labelled else list(indicators)
    # Missing data is reported below as coverage; the other warnings are re-raised so
    # that they point at the caller's line, not at this one.
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        long = latest(ids, countries, within=within, since=since)
    for warning in caught:
        if not issubclass(warning.category, MissingDataWarning):
            warnings.warn(warning.message, stacklevel=2)
    resolved = check(ids)
    label_of = (
        {resolved_id: label for label, resolved_id in zip(labelled, resolved, strict=True)}
        if labelled
        else dict(resolved)
    )
    long["label"] = long["indicator"].map(label_of)
    values = long.pivot_table(index="country", columns="label", values="value", aggfunc="first")
    years = long.pivot_table(index="country", columns="label", values="year", aggfunc="first")
    order = list(label_of.values())
    result = pd.DataFrame(index=values.index)
    for label in order:
        has = label in values.columns
        result[label] = values[label] if has else pd.NA
        result[f"{label} year"] = years[label].astype("Int64") if has else pd.NA
    iso = long.drop_duplicates("country").set_index("country")["iso3"]
    result.insert(0, "iso3", iso)
    result = result.reset_index()

    asked = [p.name for p in expand(countries)]
    have = {label: set(result.loc[result[label].notna(), "country"]) for label in order}
    every = set.intersection(*have.values()) if have else set()
    only = {label: sorted(have[label] - every) for label in order}
    none = sorted(set(asked) - set().union(*have.values()))
    result.attrs = {
        **long.attrs,
        "coverage": {"all": sorted(every), "only": only, "none": none},
    }
    keep(result, long.drop(columns="label"))
    parts = [f"{len(every)} of {len(asked)} countries have all {len(order)} indicators."]
    parts += [f"Only {label}: {_shorten(c)}." for label, c in only.items() if c]
    if none:
        parts.append(f"No data at all for {len(none)}, left out.")
    if len(every) < len(asked):
        warnings.warn(" ".join(parts), CoverageWarning, stacklevel=2)
    return result
