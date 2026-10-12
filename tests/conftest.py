from __future__ import annotations

from collections.abc import Iterator

import pytest

from undata import Transport

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
