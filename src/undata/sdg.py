"""The Sustainable Development Goals, from goal down to data you can fetch.

The platform holds the SDG framework as a tree: 17 goals, their targets, the
indicators under each target, and the data series that report each indicator.
Walk it with SDG numbers, the way a reporting mandate names them::

    un.sdg.goals()
    un.sdg.targets(16)
    un.sdg.indicators("16.1")
    un.sdg.series("16.1.2")   # the ids to pass to un.get()
"""

from __future__ import annotations

import re
from typing import Any, Final

import pandas as pd

from . import _endpoints as api
from . import _session
from .dcid import parse_dcid

__all__ = ["goals", "indicators", "series", "targets"]

_ROOT: Final = "undata/g/sdgf/Root"
_PREFIX: Final = "undata/g/sdgf/"
_CHILDREN: Final = "<-specializationOf"
_TITLE = re.compile(r"^SDG (?:Goal|Target|Indicator) [0-9A-Za-z.]+\s*[—-]\s*")


def _children(node: str | list[str]) -> dict[str, list[dict[str, Any]]]:
    """Child groups of one or more nodes in the variable-group tree."""
    nodes = [node] if isinstance(node, str) else node
    body = api.node(_session.transport(), nodes, _CHILDREN)
    return {
        n: body.get("data", {})
        .get(n, {})
        .get("arcs", {})
        .get("specializationOf", {})
        .get("nodes", [])
        for n in nodes
    }


def _number(dcid: str) -> str:
    """``undata/g/sdgf/ind-16-1-2`` -> ``16.1.2``."""
    tail = dcid.removeprefix(_PREFIX)
    return tail.split("-", 1)[1].replace("-", ".") if "-" in tail else tail


def _sort_key(number: str) -> list[tuple[int, str]]:
    return [(int(p), "") if p.isdigit() else (1_000, p) for p in number.split(".")]


def _title(name: str) -> str:
    return _TITLE.sub("", name).strip()


def _table(node: str, column: str) -> pd.DataFrame:
    kids = [k for k in _children(node)[node] if k["dcid"].startswith(_PREFIX)]
    rows = [{column: _number(k["dcid"]), "name": _title(k.get("name", ""))} for k in kids]
    frame = pd.DataFrame(rows, columns=[column, "name"])
    return frame.sort_values(column, key=lambda s: s.map(_sort_key), ignore_index=True)


def _parts(code: str | int, depth: int, what: str, example: str) -> list[str]:
    parts = str(code).strip().split(".")
    if len(parts) != depth or not all(parts):
        raise ValueError(f"{code!r} is not an SDG {what} number. Write it like {example}.")
    return parts


def goals() -> pd.DataFrame:
    """List the 17 Sustainable Development Goals.

    Returns:
        A table with columns ``goal`` and ``name``.

    Example:
        >>> import undata as un
        >>> un.sdg.goals()  # doctest: +SKIP
          goal                                               name
        0    1                    End poverty in all its forms everywhere
        ...
    """
    return _table(_ROOT, "goal")


def targets(goal: int | str) -> pd.DataFrame:
    """List the targets under one goal.

    Args:
        goal: The goal number, such as ``16``.

    Returns:
        A table with columns ``target`` (such as ``16.1``) and ``name``.
    """
    (number,) = _parts(goal, 1, "goal", "16")
    return _table(f"{_PREFIX}goal-{number}", "target")


def indicators(target: str) -> pd.DataFrame:
    """List the indicators under one target.

    Args:
        target: The target number, such as ``"16.1"`` or ``"4.a"``.

    Returns:
        A table with columns ``indicator`` (such as ``16.1.2``) and ``name``.
    """
    goal, sub = _parts(target, 2, "target", '"16.1"')
    return _table(f"{_PREFIX}target-{goal}-{sub}", "indicator")


def series(indicator: str) -> pd.DataFrame:
    """List the data series that report one SDG indicator, ready for :func:`undata.get`.

    An indicator is usually reported through several series: a count and a rate, or
    a total and its breakdowns by sex and age.

    Args:
        indicator: The indicator number, such as ``"16.1.2"``.

    Returns:
        A table with columns ``indicator`` (the id to pass to :func:`undata.get`),
        ``name``, and ``total``, which is ``True`` for a series with no breakdown.
        Totals come first.

    Example:
        >>> import undata as un
        >>> un.sdg.series("16.1.2")  # doctest: +SKIP
                       indicator                                               name  total
        0  undata/sdg/VC_DTH_TOTR  Number of total conflict-related deaths per 100...   True
        ...
    """
    goal, sub, num = _parts(indicator, 3, "indicator", '"16.1.2"')
    node = f"{_PREFIX}ind-{goal}-{sub}-{num}"
    groups = [g["dcid"] for g in _children(node)[node]]
    subgroups = [s["dcid"] for kids in _children(groups).values() for s in kids] if groups else []
    rows: dict[str, dict[str, Any]] = {}
    if subgroups:
        body = api.node(_session.transport(), subgroups, "<-memberOf")
        for entry in body.get("data", {}).values():
            for member in entry.get("arcs", {}).get("memberOf", {}).get("nodes", []):
                parsed = parse_dcid(member["dcid"])
                rows.setdefault(
                    member["dcid"],
                    {
                        "indicator": member["dcid"],
                        "name": member.get("name", ""),
                        "total": bool(parsed and parsed.is_total),
                    },
                )
    frame = pd.DataFrame(list(rows.values()), columns=["indicator", "name", "total"])
    return frame.sort_values(["total", "indicator"], ascending=[False, True], ignore_index=True)
