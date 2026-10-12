from __future__ import annotations

from urllib.parse import parse_qsl, urlsplit

import httpx
import pytest
import respx

from undata import APIError, BlockedRequestError, ConnectionFailedError, Transport
from undata._http import USER_AGENT, encode_body

from .conftest import BASE


def test_bodies_are_sent_on_one_line() -> None:
    body = encode_body({"variables": ["a", "b"], "nested": {"text": "line\nbreak"}})

    assert b"\n" not in body
    assert body == b'{"variables":["a","b"],"nested":{"text":"line\\nbreak"}}'


@respx.mock
def test_post_sends_compact_json_and_identifies_itself(transport: Transport) -> None:
    route = respx.post(f"{BASE}/api/x").mock(return_value=httpx.Response(200, json={}))

    transport.post("/api/x", {"a": [1, 2]})

    request = route.calls.last.request
    assert request.content == b'{"a":[1,2]}'
    assert request.headers["Content-Type"] == "application/json"
    assert request.headers["User-Agent"] == USER_AGENT


@respx.mock
def test_relation_expressions_are_percent_encoded(transport: Transport) -> None:
    route = respx.get(f"{BASE}/core/api/v2/node").mock(return_value=httpx.Response(200, json={}))

    transport.get("/core/api/v2/node", {"property": "<-containedInPlace+{typeOf:Country}"})

    raw_query = urlsplit(str(route.calls.last.request.url)).query
    assert "%3C-containedInPlace%2B%7BtypeOf%3ACountry%7D" in raw_query
    assert "+" not in raw_query  # a literal + would arrive as a space


@respx.mock
def test_sequences_become_repeated_keys_and_none_is_dropped(transport: Transport) -> None:
    route = respx.get(f"{BASE}/q").mock(return_value=httpx.Response(200, json={}))

    transport.get("/q", {"select": ["date", "value"], "skip": None, "date": "LATEST"})

    pairs = parse_qsl(urlsplit(str(route.calls.last.request.url)).query)
    assert pairs == [("select", "date"), ("select", "value"), ("date", "LATEST")]


@respx.mock
def test_403_explains_that_no_api_key_is_involved(transport: Transport) -> None:
    respx.get(f"{BASE}/x").mock(return_value=httpx.Response(403, text="<title>403</title>"))

    with pytest.raises(BlockedRequestError, match="not an authentication problem") as caught:
        transport.get("/x")

    assert caught.value.status == 403
    assert caught.value.body == "<title>403</title>"
    assert isinstance(caught.value, APIError)


@pytest.mark.parametrize(
    ("status", "fragment"),
    [
        (400, "malformed"),
        (404, "No such endpoint"),
        (405, "does not accept that HTTP method"),
        (500, "Retrying later"),
        (418, "answered with an error"),
    ],
)
@respx.mock
def test_error_statuses_carry_a_useful_message(
    transport: Transport, status: int, fragment: str
) -> None:
    respx.get(f"{BASE}/x").mock(return_value=httpx.Response(status, text="nope"))

    with pytest.raises(APIError, match=fragment) as caught:
        transport.get("/x")

    assert str(caught.value).endswith(f"(HTTP {status} from {BASE}/x)")


@respx.mock
def test_transient_statuses_are_retried_with_backoff(
    transport: Transport, no_retry_sleep: list[float]
) -> None:
    route = respx.get(f"{BASE}/x").mock(
        side_effect=[httpx.Response(503), httpx.Response(429), httpx.Response(200, json=[1])]
    )

    assert transport.get("/x") == [1]
    assert route.call_count == 3
    assert no_retry_sleep == [0.5, 1.0]


@respx.mock
def test_retry_after_is_respected(transport: Transport, no_retry_sleep: list[float]) -> None:
    respx.get(f"{BASE}/x").mock(
        side_effect=[httpx.Response(429, headers={"Retry-After": "7"}), httpx.Response(200, json=1)]
    )

    transport.get("/x")

    assert no_retry_sleep == [7.0]


@respx.mock
def test_retries_give_up_and_raise_the_last_status(transport: Transport) -> None:
    route = respx.get(f"{BASE}/x").mock(return_value=httpx.Response(503))

    with pytest.raises(APIError) as caught:
        transport.get("/x")

    assert caught.value.status == 503
    assert route.call_count == 3  # the first attempt plus two retries


@respx.mock
def test_dropped_connections_are_retried_then_reported(transport: Transport) -> None:
    route = respx.get(f"{BASE}/x").mock(side_effect=httpx.ConnectError("refused"))

    with pytest.raises(ConnectionFailedError, match="Could not reach") as caught:
        transport.get("/x")

    assert caught.value.url == f"{BASE}/x"
    assert route.call_count == 3


@respx.mock
def test_a_success_that_is_not_json_is_an_error(transport: Transport) -> None:
    respx.get(f"{BASE}/x").mock(return_value=httpx.Response(200, text="<html>"))

    with pytest.raises(APIError, match="not JSON"):
        transport.get("/x")


def test_a_supplied_client_is_not_closed() -> None:
    client = httpx.Client()
    with Transport(http_client=client):
        pass

    assert not client.is_closed
    client.close()


@respx.mock
def test_spaces_are_sent_as_percent_20_because_the_server_reads_plus_literally(
    transport: Transport,
) -> None:
    route = respx.get(f"{BASE}/core/api/v2/resolve").mock(return_value=httpx.Response(200, json={}))

    transport.get("/core/api/v2/resolve", {"nodes": "Viet Nam"})

    raw_query = route.calls.last.request.url.query.decode()
    assert raw_query == "nodes=Viet%20Nam"


@respx.mock
def test_a_request_without_params_has_no_query_string(transport: Transport) -> None:
    route = respx.get(f"{BASE}/x").mock(return_value=httpx.Response(200, json={}))

    transport.get("/x", {"skip": None})

    assert str(route.calls.last.request.url) == f"{BASE}/x"
