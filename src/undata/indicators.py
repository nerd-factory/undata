"""Finding indicators, and finding out what one is.

An *indicator* here is one statistical series the platform holds, identified by an
id such as ``undata/sdg/SH_STA_MORT.SEX--F``. You rarely need to type one: find it
with :func:`search`, or walk to it from an SDG target with :mod:`undata.sdg`, then
copy the id from the table. Anywhere an id is accepted, an SDG indicator number such
as ``"3.1.1"`` works too, when one series reports that indicator.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Any

import pandas as pd

from . import _endpoints as api
from . import _session, sdg
from .dcid import parse_dcid
from .errors import AmbiguousIndicatorError, IndicatorNotFoundError

__all__ = ["IndicatorInfo", "about", "metadata_url", "sdg_number", "search"]

#: Ids in the UN's own collections start with this. Search also returns copies
#: that Data Commons imported itself, which can lag the UN's series by years.
UN_PREFIX = "undata/"

#: An SDG indicator number: goal, target (a number or a letter), indicator.
SDG_NUMBER = re.compile(r"^\d{1,2}\.[0-9a-z]{1,2}\.\d{1,2}$", re.IGNORECASE)

METADATA_URL = "https://unstats.un.org/sdgs/metadata/files/Metadata-{}-{}-{}.pdf"


def _collection(indicator: str) -> str:
    """A readable name for the collection an indicator id belongs to."""
    parsed = parse_dcid(indicator)
    if indicator.startswith(UN_PREFIX) and parsed is not None:
        return parsed.agency_label
    return "Data Commons (not a UN collection)"


def _words(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", text.casefold()))


def search(
    text: str,
    *,
    all_sources: bool = False,
    breakdowns: bool = False,
    coverage: bool = True,
    limit: int = 20,
) -> pd.DataFrame:
    """Search for indicators by what they measure.

    Results whose names contain more of your words come first. Each indicator
    appears once, as its total where one exists, with a count of the breakdowns
    (by sex, age...) behind it; :func:`undata.breakdowns` lists them.

    Args:
        text: Plain words, such as ``"maternal mortality"`` or ``"access to electricity"``.
        all_sources: Also show series that Data Commons imported from elsewhere. Off
            by default: some are older copies of UN data, ranked above the UN's own.
        breakdowns: List every breakdown as its own row instead of one row per indicator.
        coverage: Add how many places have data and which years, in one extra request.
        limit: The most rows to return.

    Returns:
        A table with ``indicator`` (the id to pass to :func:`undata.get`), ``name``,
        ``source``, and with coverage on, ``places`` and ``years``. Best match first.

    Example:
        >>> import undata as un
        >>> un.search("under-five mortality")  # doctest: +SKIP
    """
    hits = api.stat_var_search(_session.transport(), text).get("statVars", [])
    wanted = _words(text)

    def rank(item: tuple[int, dict[str, Any]]) -> tuple[int, int, int]:
        position, hit = item
        parsed = parse_dcid(hit["dcid"])
        matched = len(wanted & _words(hit.get("name", "")))
        return (-matched, len(parsed.dimensions) if parsed else 0, position)

    ranked = [
        hit
        for _, hit in sorted(enumerate(hits), key=rank)
        if all_sources or hit["dcid"].startswith(UN_PREFIX)
    ]
    rows: list[dict[str, Any]] = []
    if breakdowns:
        rows = [
            {"indicator": h["dcid"], "name": h.get("name", ""), "breakdowns": 0} for h in ranked
        ]
    else:
        groups: dict[str, list[dict[str, Any]]] = {}
        for hit in ranked:
            parsed = parse_dcid(hit["dcid"])
            groups.setdefault(parsed.base if parsed else hit["dcid"], []).append(hit)
        totals = names([base for base in groups if base not in {h["dcid"] for h in ranked}])
        for base, members in groups.items():
            if base in totals:
                rows.append({"indicator": base, "name": totals[base], "breakdowns": len(members)})
            else:
                first = members[0]
                rows.append(
                    {
                        "indicator": first["dcid"],
                        "name": first.get("name", ""),
                        "breakdowns": len(members) - 1,
                    }
                )
    rows = rows[:limit]
    for row in rows:
        row["source"] = _collection(row["indicator"])
    columns = ["indicator", "name", "source"]
    if coverage and rows:
        found = _coverage([r["indicator"] for r in rows])
        for row in rows:
            row["places"], row["years"] = found.get(row["indicator"], (0, ""))
        columns += ["places", "years"]
    if not breakdowns:
        columns.append("breakdowns")
    return pd.DataFrame(rows, columns=columns)


def _coverage(ids: list[str]) -> dict[str, tuple[int, str]]:
    """Places with data and the span of years, per indicator, from one request."""
    body = api.variable_info(_session.transport(), ids)
    found: dict[str, tuple[int, str]] = {}
    for dcid in ids:
        summaries = body.get(dcid, {}).get("provenanceSummary", {})
        if not summaries:
            continue
        summary = max(summaries.values(), key=lambda s: s.get("observationCount", 0))
        series = summary.get("seriesSummary", [])
        first = min((s.get("earliestDate", "") for s in series), default="")[:4]
        last = max((s.get("latestDate", "") for s in series), default="")[:4]
        found[dcid] = (int(summary.get("timeSeriesCount", 0)), f"{first}-{last}" if first else "")
    return found


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


def _from_sdg_number(code: str) -> str:
    """The one series that reports an SDG indicator, or an error listing the options."""
    table = sdg.series(code)
    if len(table) == 1:
        return str(table["indicator"].iloc[0])
    totals = table[table["total"]]
    if len(totals) == 1:
        return str(totals["indicator"].iloc[0])
    if table.empty:
        raise IndicatorNotFoundError(code, phrase=False)
    options = totals if len(totals) else table
    raise AmbiguousIndicatorError(
        code, list(zip(options["indicator"], options["name"], strict=True))
    )


def check(indicators: str | Sequence[str]) -> dict[str, str]:
    """Validate indicator ids and return their names, in the order given.

    SDG indicator numbers such as ``"3.1.1"`` are replaced by the id of the series
    that reports them; when several do, an error lists them rather than guessing.

    Raises:
        IndicatorNotFoundError: An id is unknown, or a phrase was passed instead of an
            id. The error carries ids found by searching for it.
        AmbiguousIndicatorError: An SDG number is reported by several series.
    """
    given_list = [indicators] if isinstance(indicators, str) else list(indicators)
    if not given_list:
        raise ValueError("No indicators were given. Find one with un.search().")
    ids: list[str] = []
    for given in given_list:
        text = given.strip()
        if SDG_NUMBER.match(text):
            ids.append(_from_sdg_number(text))
        elif not text or any(ch.isspace() for ch in text):
            raise IndicatorNotFoundError(given, _suggest(given), phrase=True)
        else:
            ids.append(text)
    known = names(ids)
    for given in ids:
        if given not in known:
            raise IndicatorNotFoundError(given, _suggest(given), phrase=False)
    return {i: known[i] for i in dict.fromkeys(ids)}


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
    sdg_indicator: str = ""
    metadata: str = ""

    def __repr__(self) -> str:
        lines = [
            self.name,
            f"  id            {self.indicator}",
            f"  source        {self.source}",
            f"  unit          {self.unit or 'not stated'}",
            f"  years         {self.first_year} to {self.last_year}",
            f"  places        {self.places} countries and regions have data",
            f"  observations  {self.observations:,}",
        ]
        if self.sdg_indicator:
            lines.append(f"  SDG indicator {self.sdg_indicator}")
        if self.metadata:
            lines.append(f"  definition    {self.metadata}")
        return "\n".join(lines)


def _arc_ids(body: dict[str, Any], nodes: list[str], prop: str) -> list[str]:
    return [
        n["dcid"]
        for node in nodes
        for n in body.get("data", {}).get(node, {}).get("arcs", {}).get(prop, {}).get("nodes", [])
    ]


def sdg_number(indicator: str) -> str:
    """The SDG indicator a series reports, such as ``"3.1.1"``, or ``""`` if none."""

    def load() -> str:
        transport = _session.transport()
        subgroups = _arc_ids(api.node(transport, indicator, "->memberOf"), [indicator], "memberOf")
        if not subgroups:
            return ""
        groups = _arc_ids(
            api.node(transport, subgroups, "->specializationOf"), subgroups, "specializationOf"
        )
        if not groups:
            return ""
        parents = _arc_ids(
            api.node(transport, groups, "->specializationOf"), groups, "specializationOf"
        )
        for node in sorted(set(groups + parents)):
            if node.startswith("undata/g/sdgf/ind-"):
                return node.removeprefix("undata/g/sdgf/ind-").replace("-", ".")
        return ""

    return _session.cached(f"sdg-number:{indicator}", load)


def metadata_url(number: str) -> str:
    """The UN Statistics Division's metadata document for an SDG indicator number."""
    goal, target, index = number.split(".")
    return METADATA_URL.format(goal.zfill(2), target.lower().zfill(2), index.zfill(2))


def about(indicator: str) -> IndicatorInfo:
    """Describe an indicator: its name, source, unit and how much data exists.

    For a series that reports an SDG indicator, it also gives the indicator number
    and a link to the official metadata: the definition, method and custodian agency.

    Args:
        indicator: An id, as shown in the ``indicator`` column of :func:`search`, or
            an SDG indicator number such as ``"3.1.1"``.

    Example:
        >>> import undata as un
        >>> un.about("undata/sdg/SH_STA_MORT.SEX--F")  # doctest: +SKIP
        Maternal mortality ratio [Sex=Female]
          id            undata/sdg/SH_STA_MORT.SEX--F
          source        SDG Global Database
          ...
    """
    indicator, name = next(iter(check(indicator).items()))
    number = sdg_number(indicator)
    link = metadata_url(number) if number else ""
    info = api.variable_info(_session.transport(), indicator).get(indicator, {})
    summaries = info.get("provenanceSummary", {})
    if not summaries:
        return IndicatorInfo(indicator, name, "", "", "", "", 0, 0, number, link)

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
        sdg_indicator=number,
        metadata=link,
    )
