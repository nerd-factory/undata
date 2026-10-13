"""Pin the live platform's behaviour that undata is built around.

These call the real API, so they are excluded by default and run nightly in CI
(``pytest -m live``). A failure here does not necessarily mean undata is broken:
it means the platform changed, and the workaround it guards may now be unnecessary
or insufficient. The nightly workflow opens an issue when that happens.
"""

from __future__ import annotations

from collections.abc import Iterator

import httpx
import pytest

from undata import DEFAULT_BASE_URL, BlockedRequestError, Transport
from undata import _endpoints as ep

pytestmark = pytest.mark.live


@pytest.fixture(scope="module")
def live() -> Iterator[Transport]:
    with Transport(retries=2) as transport:
        yield transport


def test_observation_by_get_returns_values(live: Transport) -> None:
    body = ep.observation(live, "Count_Person", entities="country/BGD")

    facets = body["byVariable"]["Count_Person"]["byEntity"]["country/BGD"]["orderedFacets"]
    assert facets[0]["observations"][0]["value"] > 100_000_000


def test_select_in_a_post_body_is_still_blocked() -> None:
    """If this starts passing through, the GET-only rule can be relaxed."""
    body = {
        "variable": {"dcids": ["Count_Person"]},
        "entity": {"dcids": ["country/BGD"]},
        "select": ["date", "value", "variable", "entity"],
    }
    response = httpx.post(f"{DEFAULT_BASE_URL}/core/api/v2/observation", json=body, timeout=30)

    assert response.status_code == 403


def test_a_line_break_in_a_post_body_is_still_blocked(live: Transport) -> None:
    response = httpx.post(
        f"{DEFAULT_BASE_URL}/api/observations/series",
        content=b'{"variables":["Count_Person"],\n"entities":["country/BGD"]}',
        headers={"Content-Type": "application/json"},
        timeout=30,
    )

    assert response.status_code == 403


def test_the_transport_explains_a_block(live: Transport) -> None:
    with pytest.raises(BlockedRequestError):
        live.post("/core/api/v2/observation", {"select": ["date"]})


def test_graph_walks_page_at_500(live: Transport) -> None:
    first = live.get("/core/api/v2/node", {"nodes": "Earth", "property": "<-containedInPlace"})

    assert len(first["data"]["Earth"]["arcs"]["containedInPlace"]["nodes"]) == ep.NODE_PAGE_SIZE
    assert first.get("nextToken")


def test_resolve_finds_an_exact_country_name(live: Transport) -> None:
    body = ep.resolve(live, "Bangladesh")

    assert {"dcid": "country/BGD"} in body["entities"][0]["candidates"]


def test_missing_entities_are_absent_not_zero(live: Transport) -> None:
    body = ep.series(live, "Count_Person", ["country/BGD", "country/NOPE"])

    by_entity = body["data"]["Count_Person"]
    assert by_entity["country/BGD"]["series"]
    assert not by_entity.get("country/NOPE", {}).get("series")


def test_resolver_supplies_a_place_the_question_did_not_name(live: Transport) -> None:
    """The finding that motivates strict place handling: Bengal becomes the USA."""
    body = ep.detect_and_fulfill(live, "child mortality in Bengal")

    assert body["place"]["dcid"] == "country/USA"


def test_plus_in_a_query_string_is_not_read_as_a_space(live: Transport) -> None:
    """Why the transport sends %20. If the echo becomes "Viet Nam", httpx's default is safe."""
    plus = httpx.get(
        f"{DEFAULT_BASE_URL}/core/api/v2/resolve?nodes=Viet+Nam&property=%3C-description-%3Edcid",
        timeout=30,
    ).json()
    ours = ep.resolve(live, "Viet Nam")

    assert plus["entities"][0]["node"] == "Viet+Nam"
    assert ours["entities"][0]["node"] == "Viet Nam"


def test_search_ranks_the_base_import_above_the_un_series(live: Transport) -> None:
    """The top hit for maternal mortality is Data Commons' own copy, not the UN's.

    ``sdg/...`` comes from ``dc/base/UN_SDG`` and lags the UN's ``undata/sdg/...``
    series by years, under the same provenance URL. The UN series is in the results,
    further down. Search results must be steered to the ``undata/`` collection.
    """
    hits = [hit["dcid"] for hit in ep.stat_var_search(live, "maternal mortality")["statVars"]]

    assert hits[0] == "sdg/SH_STA_MORT.SEX--F"
    assert hits.index("undata/sdg/SH_STA_MORT.SEX--F") > 0


@pytest.mark.parametrize("code", ["ESH", "GRC", "SVN"])
def test_a_get_mentioning_some_countries_is_blocked_but_post_is_not(code: str) -> None:
    """Why data is fetched by POST: ESH, GRC and SVN read as command names to the firewall."""
    get = httpx.get(
        f"{DEFAULT_BASE_URL}/core/api/v2/node?nodes=country%2F{code}&property=-%3Ename", timeout=30
    )
    post = httpx.post(
        f"{DEFAULT_BASE_URL}/api/observations/series",
        json={"variables": ["Count_Person"], "entities": [f"country/{code}"]},
        timeout=30,
    )

    assert get.status_code == 403
    assert post.status_code == 200
