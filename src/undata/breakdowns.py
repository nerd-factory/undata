"""Breakdowns: the same indicator by sex, by age, by wealth, and so on.

On the platform each indicator belongs to a group whose sub-groups hold every slice
of it. :func:`breakdowns` lists them as a table; ``un.get(..., by="sex")`` fetches
one dimension's slices side by side.

One caution travels with every breakdown: the "unknown" category (an unknown age, an
unknown sex) is published as a slice of its own. The named slices therefore do not
always add up to the total, and undata never forces them to.
"""

from __future__ import annotations

import re
from typing import Any

import pandas as pd

from . import _endpoints as api
from . import _session
from .dcid import parse_dcid
from .errors import IndicatorNotFoundError
from .indicators import check

__all__ = ["breakdowns"]

_PAIR = re.compile(r"\[([^\]]*)\]\s*$")


def _arc(body: dict[str, Any], node: str, prop: str) -> list[dict[str, Any]]:
    nodes: list[dict[str, Any]] = (
        body.get("data", {}).get(node, {}).get("arcs", {}).get(prop, {}).get("nodes", [])
    )
    return nodes


def _labels(name: str, dimensions: list[str]) -> dict[str, str]:
    """Readable values per dimension, read from the bracket at the end of a name.

    ``"Deaths [Age=Under 18 years old, Sex=Female]"`` with dimensions AGE and SEX
    gives ``{"AGE": "Under 18 years old", "SEX": "Female"}``. The name lists the
    dimensions in the same order as the identifier does.
    """
    match = _PAIR.search(name)
    if not match:
        return {}
    values = [part.split("=", 1)[1].strip() for part in match.group(1).split(", ") if "=" in part]
    return dict(zip(dimensions, values, strict=False)) if len(values) == len(dimensions) else {}


def _column(dimension: str) -> str:
    """``WEALTH_QUANTILE`` -> ``wealth quantile``: a readable column name."""
    return dimension.lower().replace("_", " ")


#: Graph lookups per request, to keep GET query strings short.
_BATCH = 40
#: How many levels to walk down from an indicator's group. The platform nests context
#: groups (by sex, by urbanization...) under the group, and sub-groups under those.
_DEPTH = 4


def _children(nodes: list[str], prop: str) -> dict[str, list[dict[str, Any]]]:
    """``prop`` arcs of many nodes, fetched in batches."""
    transport = _session.transport()
    found: dict[str, list[dict[str, Any]]] = {}
    for start in range(0, len(nodes), _BATCH):
        batch = nodes[start : start + _BATCH]
        body = api.node(transport, batch, prop)
        arc = prop.lstrip("<-")
        for node in batch:
            found[node] = _arc(body, node, arc)
    return found


def _members(indicator: str) -> list[tuple[str, str]]:
    """Every slice of the indicator, as (id, name). Cached per session.

    The indicator's group is named after it (``undata/sdg/X`` belongs to
    ``undata/g/sdg/X``). Every group below it is walked, and their members collected.
    """

    def load() -> list[tuple[str, str]]:
        parsed = parse_dcid(indicator)
        if parsed is None:
            return []
        top = f"{parsed.namespace}/g/{parsed.agency}/{parsed.code}"
        groups: list[str] = [top]
        frontier, seen = [top], {top}
        for _ in range(_DEPTH):
            below = _children(frontier, "<-specializationOf")
            fresh: list[str] = []
            for node in frontier:
                for child in below.get(node, []):
                    if child["dcid"] not in seen:
                        seen.add(child["dcid"])
                        fresh.append(child["dcid"])
            frontier = fresh
            if not frontier:
                break
            groups += frontier
        found: dict[str, str] = {}
        for nodes in _children(groups, "<-memberOf").values():
            for n in nodes:
                found.setdefault(n["dcid"], n.get("name", n["dcid"]))
        return sorted(found.items())

    return _session.cached(f"breakdowns:{indicator}", load)


def breakdowns(indicator: str) -> pd.DataFrame:
    """List every breakdown of an indicator: by sex, age, wealth and so on.

    Args:
        indicator: An indicator id, or an SDG indicator number such as ``"16.1.2"``.

    Returns:
        A table with ``indicator`` (the id to pass to :func:`undata.get`), ``name``,
        and one column per dimension (``sex``, ``age``...) holding readable values.
        The total, with no breakdown, comes first.

    Example:
        >>> import undata as un
        >>> un.breakdowns("undata/sdg/VC_DTH_TOTN")  # doctest: +SKIP
    """
    resolved = next(iter(check(indicator)))
    rows: list[dict[str, Any]] = []
    for dcid, name in _members(resolved):
        parsed = parse_dcid(dcid)
        codes = {d.name: d.value for d in parsed.dimensions} if parsed else {}
        labels = _labels(name, list(codes))
        row: dict[str, Any] = {"indicator": dcid, "name": name}
        for dim, code in codes.items():
            row[_column(dim)] = labels.get(dim, code)
        rows.append(row)
    frame = pd.DataFrame(rows)
    if frame.empty:
        return pd.DataFrame(columns=["indicator", "name"])
    dim_columns = [c for c in frame.columns if c not in ("indicator", "name")]
    frame["_dims"] = frame[dim_columns].notna().sum(axis=1) if dim_columns else 0
    frame = frame.sort_values(["_dims", "indicator"], ignore_index=True).drop(columns="_dims")
    return frame[["indicator", "name", *dim_columns]]


def slices_by(indicator: str, dimension: str) -> dict[str, str]:
    """The slices of ``indicator`` that add exactly one ``dimension``, as {id: label}.

    The indicator's own dimensions are kept, so ``CME_MR.AGE--Y0T4`` by sex gives the
    under-five rate for each sex, not every age band for each sex.

    Raises:
        IndicatorNotFoundError: The indicator has no breakdown by that dimension. The
            message lists the dimensions it does have.
    """
    wanted = dimension.strip().upper().replace(" ", "_")
    base = parse_dcid(indicator)
    if base is None:
        raise IndicatorNotFoundError(indicator, phrase=False)
    own = {d.name: d.value for d in base.dimensions}
    found: dict[str, str] = {}
    available: set[str] = set()
    for dcid, name in _members(indicator):
        parsed = parse_dcid(dcid)
        if parsed is None or parsed.base != base.base:
            continue
        dims = {d.name: d.value for d in parsed.dimensions}
        available.update(set(dims) - set(own))
        extra = set(dims) - set(own)
        if extra == {wanted} and all(dims.get(k) == v for k, v in own.items()):
            label = _labels(name, [d.name for d in parsed.dimensions]).get(wanted, dims[wanted])
            found[dcid] = label
    if not found:
        options = ", ".join(sorted(_column(a) for a in available)) or "none"
        raise ValueError(
            f"{indicator} has no breakdown by {dimension!r}. Breakdowns it has: {options}. "
            "See un.breakdowns() for the full list."
        )
    return dict(sorted(found.items(), key=lambda kv: kv[1]))
