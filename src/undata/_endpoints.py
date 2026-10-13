"""One thin wrapper per API route. No interpretation happens here.

These return the API's JSON as-is; the public modules built on top of them are
where missing data, provenance and place resolution get handled. Keeping this
layer dumb means a change on the platform shows up in exactly one place.

The routes split across two surfaces:

* ``/core/api/v2/*`` is the Data Commons REST v2 API (graph, observations, resolve).
* ``/api/*`` is the website's own API, which carries search and variable metadata
  that REST v2 does not expose.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, Final

from ._http import Transport

#: Fields requested from the observation endpoint. Without ``select`` it returns
#: an empty shell, and with ``select`` in a POST body the firewall answers 403,
#: which is why :func:`observation` is GET-only.
OBSERVATION_FIELDS: Final = ("date", "value", "variable", "entity", "facet")

#: Graph walks return at most this many values per page and set ``nextToken``.
NODE_PAGE_SIZE: Final = 500

#: Upper bound on pages followed for one graph walk; protects against a cycle.
MAX_NODE_PAGES: Final = 200

JSON = dict[str, Any]


def _as_list(value: str | Sequence[str]) -> list[str]:
    return [value] if isinstance(value, str) else list(value)


def observation(
    transport: Transport,
    variables: str | Sequence[str],
    *,
    entities: str | Sequence[str] | None = None,
    entity_expression: str | None = None,
    date: str = "LATEST",
) -> JSON:
    """Fetch observations from ``/core/api/v2/observation``, always by GET.

    Pass either explicit ``entities`` or an ``entity_expression`` such as
    ``africa<-containedInPlace+{typeOf:Country}``. ``date`` is ``"LATEST"``, ``""``
    for every date, or a single date like ``"2020"``. Note that ``"LATEST"`` means
    each entity's own most recent date, which differs between countries.
    """
    if (entities is None) == (entity_expression is None):
        raise ValueError("Pass exactly one of entities or entity_expression.")
    result: JSON = transport.get(
        "/core/api/v2/observation",
        {
            "date": date,
            "variable.dcids": _as_list(variables),
            "entity.dcids": None if entities is None else _as_list(entities),
            "entity.expression": entity_expression,
            "select": OBSERVATION_FIELDS,
        },
    )
    return result


def node(transport: Transport, nodes: str | Sequence[str], prop: str) -> JSON:
    """Follow a relation expression from ``/core/api/v2/node``, across every page.

    The API caps each page at 500 values and returns a ``nextToken``; this follows
    the tokens and merges the pages, so the result is the complete answer.
    """
    params: dict[str, str | list[str] | None] = {"nodes": _as_list(nodes), "property": prop}
    merged: JSON = transport.get("/core/api/v2/node", params)
    token = merged.pop("nextToken", None)
    pages = 1
    while token:
        if pages >= MAX_NODE_PAGES:
            raise RuntimeError(f"Stopped after {MAX_NODE_PAGES} pages of {prop!r}.")
        page: JSON = transport.get("/core/api/v2/node", {**params, "nextToken": token})
        _merge_node_page(merged, page)
        token = page.get("nextToken")
        pages += 1
    return merged


def _merge_node_page(merged: JSON, page: JSON) -> None:
    """Append one page's arc values onto the accumulated result, in place."""
    for dcid, entry in page.get("data", {}).items():
        target = merged.setdefault("data", {}).setdefault(dcid, {})
        for arc, values in entry.get("arcs", {}).items():
            existing = target.setdefault("arcs", {}).setdefault(arc, {"nodes": []})
            existing.setdefault("nodes", []).extend(values.get("nodes", []))
        if "properties" in entry:
            props = target.setdefault("properties", [])
            props.extend(p for p in entry["properties"] if p not in props)


def resolve(
    transport: Transport,
    nodes: str | Sequence[str],
    prop: str = "<-description->dcid",
) -> JSON:
    """Resolve names or other identifiers to dcids via ``/core/api/v2/resolve``."""
    result: JSON = transport.get(
        "/core/api/v2/resolve", {"nodes": _as_list(nodes), "property": prop}
    )
    return result


def series(
    transport: Transport,
    variables: str | Sequence[str],
    entities: str | Sequence[str],
) -> JSON:
    """Fetch full time series for every variable/entity pair from the website API.

    Entities with no data are absent from the response rather than empty.
    """
    result: JSON = transport.post(
        "/api/observations/series",
        {"variables": _as_list(variables), "entities": _as_list(entities)},
    )
    return result


def stat_var_search(transport: Transport, query: str) -> JSON:
    """Search statistical variables by text.

    Results include Data Commons' base variables (``Count_Person``) as well as the
    UN collections (``undata/...``).
    """
    result: JSON = transport.get("/api/stats/stat-var-search", {"query": query})
    return result


def variable_info(transport: Transport, dcids: str | Sequence[str]) -> JSON:
    """Coverage and provenance summary per variable, from ``/api/variable/info``."""
    result: JSON = transport.get("/api/variable/info", {"dcids": _as_list(dcids)})
    return result


def place_names(transport: Transport, dcids: str | Sequence[str]) -> dict[str, str]:
    """Display names for place dcids."""
    result: dict[str, str] = transport.get("/api/place/name", {"dcids": _as_list(dcids)})
    return result


def variable_group_info(transport: Transport, dcid: str) -> JSON:
    """Children and indicator counts for a node in the variable-group tree."""
    result: JSON = transport.post("/api/variable-group/info", {"dcid": dcid, "entities": []})
    return result


def detect_and_fulfill(transport: Transport, question: str) -> JSON:
    """Run a question through the site's natural-language resolver.

    The resolver always commits to a place. When the question names none it
    recognises, it supplies one silently, so the result must be inspected before
    it is trusted.
    """
    result: JSON = transport.post(
        "/api/explore/detect-and-fulfill", {"contextHistory": []}, params={"q": question}
    )
    return result
