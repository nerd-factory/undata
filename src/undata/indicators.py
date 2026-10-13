"""Finding indicators, and finding out what one is.

An *indicator* here is one statistical series the platform holds, identified by an
id such as ``undata/sdg/SH_STA_MORT.SEX--F``. You rarely need to type one: find it
with :func:`search`, or walk to it from an SDG target with :mod:`undata.sdg`, then
copy the id from the table.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Any

import pandas as pd

from . import _endpoints as api
from . import _session
from .dcid import parse_dcid
from .errors import IndicatorNotFoundError

__all__ = ["IndicatorInfo", "about", "search"]

#: Ids in the UN's own collections start with this. Search also returns copies
#: that Data Commons imported itself, which can lag the UN's series by years.
UN_PREFIX = "undata/"


def _collection(indicator: str) -> str:
    """A readable name for the collection an indicator id belongs to."""
    parsed = parse_dcid(indicator)
    if indicator.startswith(UN_PREFIX) and parsed is not None:
        return parsed.agency_label
    return "Data Commons (not a UN collection)"


def _words(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", text.casefold()))


def search(text: str, *, all_sources: bool = False, limit: int = 20) -> pd.DataFrame:
    """Search for indicators by what they measure.

    Results whose names contain more of your words come first, and among those,
    series with fewer breakdowns (a total before "by sex and age"). The platform's
    own ranking is kept as the tie-breaker.

    Args:
        text: Plain words, such as ``"maternal mortality"`` or ``"access to electricity"``.
        all_sources: Also show series that Data Commons imported from elsewhere. Off
            by default: some are older copies of UN data, ranked above the UN's own.
        limit: The most rows to return.

    Returns:
        A table with columns ``indicator`` (the id to pass to :func:`undata.get`),
        ``name`` and ``source``, best match first.

    Example:
        >>> import undata as un
        >>> un.search("maternal mortality")  # doctest: +SKIP
                              indicator                                   name  ...
        0  undata/sdg/SH_STA_MORT.SEX--F  Maternal mortality ratio [Sex=Female]  ...
    """
    hits = api.stat_var_search(_session.transport(), text).get("statVars", [])
    wanted = _words(text)

    def rank(item: tuple[int, dict[str, Any]]) -> tuple[int, int, int]:
        position, hit = item
        parsed = parse_dcid(hit["dcid"])
        matched = len(wanted & _words(hit.get("name", "")))
        return (-matched, len(parsed.dimensions) if parsed else 0, position)

    kept = [
        hit
        for _, hit in sorted(enumerate(hits), key=rank)
        if all_sources or hit["dcid"].startswith(UN_PREFIX)
    ]
    rows = [
        {"indicator": hit["dcid"], "name": hit.get("name", ""), "source": _collection(hit["dcid"])}
        for hit in kept[:limit]
    ]
    return pd.DataFrame(rows, columns=["indicator", "name", "source"])


def _first_name(entry: dict[str, Any], fallback: str) -> str:
    nodes = entry.get("arcs", {}).get("name", {}).get("nodes", [])
    for node in nodes:
        value = node.get("value", "")
        if value and value != fallback:
            return str(value)
    return fallback


def names(ids: Iterable[str]) -> dict[str, str]:
    """Display names for graph ids (indicators, sources, units), cached per session.

    Ids with no name in the graph are absent from the result.
    """
    wanted = list(dict.fromkeys(ids))
    cache: dict[str, str | None] = _session.cached("names", dict)
    missing = [i for i in wanted if i not in cache]
    if missing:
        body = api.node(_session.transport(), missing, "->name")
        for node_id in missing:
            entry = body.get("data", {}).get(node_id, {})
            name = _first_name(entry, node_id) if entry else None
            cache[node_id] = None if name == node_id else name
    return {i: name for i in wanted if (name := cache.get(i))}


def source_label(provenance_id: str) -> str:
    """A readable name for a data source, flagging copies Data Commons imported itself."""
    name = names([provenance_id]).get(provenance_id, provenance_id.rsplit("/", 1)[-1])
    if provenance_id.startswith(UN_PREFIX):
        return name
    return f"{name} (Data Commons copy)"


def check(indicators: str | Sequence[str]) -> dict[str, str]:
    """Validate indicator ids and return their names, in the order given.

    Raises:
        IndicatorNotFoundError: An id is unknown, or a phrase was passed instead of an
            id. The error carries ids found by searching for it.
    """
    ids = [indicators] if isinstance(indicators, str) else list(indicators)
    if not ids:
        raise ValueError("No indicators were given. Find one with un.search().")
    for given in ids:
        if not given.strip() or any(ch.isspace() for ch in given.strip()):
            raise IndicatorNotFoundError(given, _suggest(given), phrase=True)
    known = names(ids)
    for given in ids:
        if given not in known:
            raise IndicatorNotFoundError(given, _suggest(given), phrase=False)
    return {i: known[i] for i in ids}


def _suggest(text: str) -> list[str]:
    parsed = parse_dcid(text)
    query = parsed.code if parsed else text
    try:
        return list(search(query, limit=3)["indicator"])
    except Exception:  # suggestions are a courtesy; never let them mask the real error
        return []


@dataclass(frozen=True, slots=True)
class IndicatorInfo:
    """What an indicator is, where it comes from, and how much data it has."""

    indicator: str
    name: str
    source: str
    unit: str
    first_year: str
    last_year: str
    places: int
    observations: int

    def __repr__(self) -> str:
        return "\n".join(
            [
                self.name,
                f"  id            {self.indicator}",
                f"  source        {self.source}",
                f"  unit          {self.unit or 'not stated'}",
                f"  years         {self.first_year} to {self.last_year}",
                f"  places        {self.places} countries and regions have data",
                f"  observations  {self.observations:,}",
            ]
        )


def about(indicator: str) -> IndicatorInfo:
    """Describe an indicator: its name, source, unit and how much data exists.

    Args:
        indicator: An id, as shown in the ``indicator`` column of :func:`search`.

    Example:
        >>> import undata as un
        >>> un.about("undata/sdg/SH_STA_MORT.SEX--F")  # doctest: +SKIP
        Maternal mortality ratio [Sex=Female]
          id            undata/sdg/SH_STA_MORT.SEX--F
          source        SDG Global Database
          ...
    """
    name = check(indicator)[indicator]
    info = api.variable_info(_session.transport(), indicator).get(indicator, {})
    summaries = info.get("provenanceSummary", {})
    if not summaries:
        return IndicatorInfo(indicator, name, "", "", "", "", 0, 0)

    provenance, summary = max(summaries.items(), key=lambda kv: kv[1].get("observationCount", 0))
    series = summary.get("seriesSummary", [])
    unit_id = next((s.get("seriesKey", {}).get("unit") for s in series if s.get("seriesKey")), None)
    unit = names([unit_id]).get(unit_id, unit_id) if unit_id else ""
    return IndicatorInfo(
        indicator=indicator,
        name=name,
        source=source_label(provenance),
        unit=unit or "",
        first_year=min((s.get("earliestDate", "") for s in series), default="")[:4],
        last_year=max((s.get("latestDate", "") for s in series), default="")[:4],
        places=int(summary.get("timeSeriesCount", 0)),
        observations=int(summary.get("observationCount", 0)),
    )
