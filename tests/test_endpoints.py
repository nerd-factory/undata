from __future__ import annotations

import json
from urllib.parse import parse_qsl, urlsplit

import httpx
import pytest
import respx

from undata import Transport
from undata import _endpoints as ep

from .conftest import BASE


def _query(route: respx.Route) -> list[tuple[str, str]]:
    return parse_qsl(urlsplit(str(route.calls.last.request.url)).query, keep_blank_values=True)


@respx.mock
def test_observation_uses_get_because_a_select_body_is_blocked(transport: Transport) -> None:
    route = respx.get(f"{BASE}/core/api/v2/observation").mock(
        return_value=httpx.Response(200, json={"byVariable": {}})
    )

    ep.observation(transport, "Count_Person", entities=["country/BGD", "country/NPL"])

    assert _query(route) == [
        ("date", "LATEST"),
        ("variable.dcids", "Count_Person"),
        ("entity.dcids", "country/BGD"),
        ("entity.dcids", "country/NPL"),
        ("select", "date"),
        ("select", "value"),
        ("select", "variable"),
        ("select", "entity"),
    ]


@respx.mock
def test_observation_by_expression(transport: Transport) -> None:
    route = respx.get(f"{BASE}/core/api/v2/observation").mock(
        return_value=httpx.Response(200, json={})
    )

    ep.observation(transport, ["a", "b"], entity_expression="africa<-x", date="")

    query = dict(_query(route))
    assert query["entity.expression"] == "africa<-x"
    assert query["date"] == ""
    assert "entity.dcids" not in query


@pytest.mark.parametrize(
    "kwargs", [{}, {"entities": "country/BGD", "entity_expression": "africa<-x"}]
)
def test_observation_needs_exactly_one_entity_selector(
    transport: Transport, kwargs: dict[str, str]
) -> None:
    with pytest.raises(ValueError, match="exactly one"):
        ep.observation(transport, "Count_Person", **kwargs)


def _page(values: list[str], token: str | None) -> httpx.Response:
    body: dict[str, object] = {
        "data": {"Earth": {"arcs": {"containedInPlace": {"nodes": [{"dcid": v} for v in values]}}}}
    }
    if token:
        body["nextToken"] = token
    return httpx.Response(200, json=body)


@respx.mock
def test_node_follows_next_token_and_merges_pages(transport: Transport) -> None:
    route = respx.get(f"{BASE}/core/api/v2/node").mock(
        side_effect=[_page(["a", "b"], "t1"), _page(["c"], "t2"), _page(["d"], None)]
    )

    result = ep.node(transport, "Earth", "<-containedInPlace")

    nodes = result["data"]["Earth"]["arcs"]["containedInPlace"]["nodes"]
    assert [n["dcid"] for n in nodes] == ["a", "b", "c", "d"]
    assert "nextToken" not in result
    assert route.call_count == 3
    assert ("nextToken", "t2") in _query(route)


@respx.mock
def test_node_merges_property_lists_without_duplicates(transport: Transport) -> None:
    respx.get(f"{BASE}/core/api/v2/node").mock(
        side_effect=[
            httpx.Response(200, json={"data": {"X": {"properties": ["a", "b"]}}, "nextToken": "t"}),
            httpx.Response(200, json={"data": {"X": {"properties": ["b", "c"]}}}),
        ]
    )

    result = ep.node(transport, "X", "->")

    assert result["data"]["X"]["properties"] == ["a", "b", "c"]


@respx.mock
def test_node_stops_on_a_token_cycle(transport: Transport, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ep, "MAX_NODE_PAGES", 3)
    respx.get(f"{BASE}/core/api/v2/node").mock(return_value=_page(["x"], "same"))

    with pytest.raises(RuntimeError, match="Stopped after 3 pages"):
        ep.node(transport, "Earth", "<-containedInPlace")


@respx.mock
def test_series_posts_a_compact_body(transport: Transport) -> None:
    route = respx.post(f"{BASE}/api/observations/series").mock(
        return_value=httpx.Response(200, json={"data": {}})
    )

    ep.series(transport, "Count_Person", ["country/BGD"])

    sent = route.calls.last.request.content
    assert json.loads(sent) == {"variables": ["Count_Person"], "entities": ["country/BGD"]}
    assert b"select" not in sent


@respx.mock
def test_detect_and_fulfill_puts_the_question_in_the_query(transport: Transport) -> None:
    route = respx.post(f"{BASE}/api/explore/detect-and-fulfill").mock(
        return_value=httpx.Response(200, json={})
    )

    ep.detect_and_fulfill(transport, "child mortality in Bengal")

    assert _query(route) == [("q", "child mortality in Bengal")]
    assert route.calls.last.request.content == b'{"contextHistory":[]}'


@respx.mock
def test_simple_get_routes(transport: Transport) -> None:
    resolve = respx.get(f"{BASE}/core/api/v2/resolve").mock(
        return_value=httpx.Response(200, json={})
    )
    search = respx.get(f"{BASE}/api/stats/stat-var-search").mock(
        return_value=httpx.Response(200, json={})
    )
    info = respx.get(f"{BASE}/api/variable/info").mock(return_value=httpx.Response(200, json={}))
    names = respx.get(f"{BASE}/api/place/name").mock(return_value=httpx.Response(200, json={}))
    group = respx.post(f"{BASE}/api/variable-group/info").mock(
        return_value=httpx.Response(200, json={})
    )

    ep.resolve(transport, "Bangladesh")
    ep.stat_var_search(transport, "child mortality")
    ep.variable_info(transport, ["a", "b"])
    ep.place_names(transport, "country/BGD")
    ep.variable_group_info(transport, "dc/g/Root")

    assert _query(resolve) == [("nodes", "Bangladesh"), ("property", "<-description->dcid")]
    assert _query(search) == [("query", "child mortality")]
    assert _query(info) == [("dcids", "a"), ("dcids", "b")]
    assert _query(names) == [("dcids", "country/BGD")]
    assert json.loads(group.calls.last.request.content) == {"dcid": "dc/g/Root", "entities": []}
