from __future__ import annotations

from collections.abc import Iterator

import pytest

from undata import Transport, _session

from .fake_api import FakeAPI

BASE = "https://example.test"


@pytest.fixture(autouse=True)
def no_retry_sleep(monkeypatch: pytest.MonkeyPatch) -> list[float]:
    """Record retry delays instead of sleeping through them."""
    delays: list[float] = []
    monkeypatch.setattr("undata._http.time.sleep", delays.append)
    return delays


@pytest.fixture
def transport() -> Iterator[Transport]:
    with Transport(base_url=BASE, retries=2) as t:
        yield t


@pytest.fixture
def fake(monkeypatch: pytest.MonkeyPatch) -> FakeAPI:
    """Swap the platform for an in-memory fake and start from an empty cache."""
    api = FakeAPI()
    for name in ("node", "series", "stat_var_search", "variable_info"):
        monkeypatch.setattr(f"undata._endpoints.{name}", getattr(api, name))
    monkeypatch.setattr("undata._endpoints.detect_and_fulfill", api.detect_and_fulfill)
    monkeypatch.setattr(_session._State, "transport", object())
    monkeypatch.setattr(_session._State, "cache", {})
    return api
