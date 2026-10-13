"""Transport: the only module that talks to the network.

It exists to make the platform's request traps impossible to trip over:

* A line break anywhere in a POST body is answered with 403, so bodies are always
  serialised compactly here rather than left to the caller.
* A POST body containing a ``"select"`` key is also answered with 403, so the
  observation endpoint is only ever called with GET (see ``_endpoints``).
* Relation expressions (``->``, ``<-``, ``+``, ``{typeOf:Country}``) must be
  percent-encoded or the API answers 400. Query strings are built here with every
  reserved character percent-encoded, ``+`` included.
* Any GET whose query string contains the word ``ESH`` (Western Sahara's country
  code) is answered with 403: the firewall mistakes it for the ``esh`` shell. The
  friendly functions therefore fetch data by POST (see ``data._collect``).
* The server does not decode ``+`` as a space in a query string: ``nodes=Viet+Nam``
  reaches it as ``Viet+Nam``. Spaces are therefore sent as ``%20``, never ``+``,
  which is what httpx would do by default.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import os
import sys
import time
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, Final
from urllib.parse import quote, urlencode

import httpx

from ._version import __version__
from .errors import APIError, BlockedRequestError, ConnectionFailedError

DEFAULT_BASE_URL: Final = "https://unsd-datacommons.gcp.un-icc.cloud"
DEFAULT_TIMEOUT: Final = 30.0
DEFAULT_RETRIES: Final = 3

USER_AGENT: Final = f"undata/{__version__} (+https://github.com/nerd-factory/undata)"

#: Statuses worth retrying: rate limiting and transient upstream failures.
RETRY_STATUSES: Final = frozenset({429, 502, 503, 504})

#: A query value is a string, or a sequence of strings sent as repeated keys.
QueryValue = str | Sequence[str]

_BLOCKED_MESSAGE: Final = (
    "The data.un.org firewall refused this request. No API key exists or is needed, "
    "so this is not an authentication problem. The firewall is known to refuse a POST "
    'body containing a line break or a "select" key, and any GET request whose query '
    "contains the word ESH (Western Sahara's country code), which it mistakes for a "
    "shell command. undata's own functions avoid all three; if one of them raised this, "
    "the rules have changed. Please report it at "
    "https://github.com/nerd-factory/undata/issues with the URL above."
)


def encode_body(body: Mapping[str, Any]) -> bytes:
    """Serialise a JSON body on a single line, which this deployment requires."""
    return json.dumps(body, separators=(",", ":"), ensure_ascii=False).encode()


def query_string(params: Mapping[str, QueryValue | None]) -> str:
    """Encode params as a query string the way this deployment needs.

    Sequence values become repeated keys, ``None`` values are dropped, and every
    reserved character is percent-encoded. Spaces become ``%20``: the server reads
    ``+`` literally.

    Example:
        >>> query_string({"nodes": ["Viet Nam", "Chad"], "property": "<-a+", "x": None})
        'nodes=Viet%20Nam&nodes=Chad&property=%3C-a%2B'
    """
    pairs: list[tuple[str, str]] = []
    for key, value in params.items():
        if value is None:
            continue
        if isinstance(value, str):
            pairs.append((key, value))
        else:
            pairs.extend((key, item) for item in value)
    return urlencode(pairs, quote_via=quote, safe="")


def default_cache_dir() -> Path:
    """Where cached responses go: the platform's usual cache folder, under ``undata``."""
    if sys.platform == "win32":
        root = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    elif sys.platform == "darwin":
        root = Path.home() / "Library" / "Caches"
    else:
        root = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
    return root / "undata"


class Transport:
    """A synchronous HTTP transport with retries, explanatory errors and a disk cache.

    Args:
        base_url: Root of the Data Commons deployment.
        timeout: Seconds to wait for each response.
        retries: How many times to retry a 429, 502, 503 or 504, or a dropped
            connection, before giving up.
        http_client: An ``httpx.Client`` to use instead of creating one. Useful for
            proxies, custom certificates, and tests.
        cache_dir: Keep successful responses here and reuse them, so a notebook that
            runs again does not ask again. ``None`` turns the cache off.
        cache_hours: How long a cached response stays fresh.
    """

    def __init__(
        self,
        *,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = DEFAULT_TIMEOUT,
        retries: int = DEFAULT_RETRIES,
        http_client: httpx.Client | None = None,
        cache_dir: str | Path | None = None,
        cache_hours: float = 24,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.retries = retries
        self.cache_dir = Path(cache_dir).expanduser() if cache_dir is not None else None
        self.cache_seconds = cache_hours * 3600
        self._owns_client = http_client is None
        self._client = http_client or httpx.Client(
            timeout=timeout,
            headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
            follow_redirects=True,
        )

    def get(self, path: str, params: Mapping[str, QueryValue | None] | None = None) -> Any:
        """GET ``path`` and return the decoded JSON body."""
        request = self._client.build_request("GET", self._url(path, params))
        return self._send(request)

    def post(
        self,
        path: str,
        body: Mapping[str, Any],
        params: Mapping[str, QueryValue | None] | None = None,
    ) -> Any:
        """POST a single-line JSON ``body`` to ``path`` and return the decoded JSON."""
        request = self._client.build_request(
            "POST",
            self._url(path, params),
            content=encode_body(body),
            headers={"Content-Type": "application/json"},
        )
        return self._send(request)

    def close(self) -> None:
        """Close the underlying connection pool, if this transport created it."""
        if self._owns_client:
            self._client.close()

    def __enter__(self) -> Transport:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    def _url(self, path: str, params: Mapping[str, QueryValue | None] | None) -> str:
        url = f"{self.base_url}/{path.lstrip('/')}"
        query = query_string(params or {})
        return f"{url}?{query}" if query else url

    def _cache_file(self, request: httpx.Request) -> Path | None:
        if self.cache_dir is None:
            return None
        key = hashlib.sha256(f"{request.method} {request.url}\n".encode() + request.content)
        return self.cache_dir / f"{key.hexdigest()}.json"

    def _send(self, request: httpx.Request) -> Any:
        cached = self._cache_file(request)
        fresh = cached is not None and cached.exists()
        if fresh and cached and time.time() - cached.stat().st_mtime < self.cache_seconds:
            with contextlib.suppress(ValueError, OSError):
                return json.loads(cached.read_text(encoding="utf-8"))
        result = self._send_live(request)
        if cached is not None:
            with contextlib.suppress(OSError):  # a cache that cannot be written is no cache
                cached.parent.mkdir(parents=True, exist_ok=True)
                partial = cached.with_suffix(".tmp")
                partial.write_text(json.dumps(result), encoding="utf-8")
                partial.replace(cached)
        return result

    def clear_cache(self) -> int:
        """Delete every cached response. Returns how many were deleted."""
        if self.cache_dir is None or not self.cache_dir.exists():
            return 0
        removed = 0
        for file in self.cache_dir.glob("*.json"):
            with contextlib.suppress(OSError):
                file.unlink()
                removed += 1
        return removed

    def _send_live(self, request: httpx.Request) -> Any:
        url = str(request.url)
        for attempt in range(self.retries + 1):
            last_attempt = attempt == self.retries
            try:
                response = self._client.send(request)
            except httpx.TransportError as exc:
                if last_attempt:
                    raise ConnectionFailedError(
                        f"Could not reach data.un.org: {exc}", url=url
                    ) from exc
                _sleep_before_retry(attempt, None)
                continue

            if response.status_code in RETRY_STATUSES and not last_attempt:
                _sleep_before_retry(attempt, response.headers.get("Retry-After"))
                continue
            return _decode(response, url)

        raise AssertionError("unreachable: the final attempt always returns or raises")


def _decode(response: httpx.Response, url: str) -> Any:
    status = response.status_code
    body = response.text[:500]
    if status == httpx.codes.FORBIDDEN:
        raise BlockedRequestError(_BLOCKED_MESSAGE, status=status, url=url, body=body)
    if status >= httpx.codes.BAD_REQUEST:
        raise APIError(_status_message(status), status=status, url=url, body=body)
    try:
        return response.json()
    except ValueError as exc:
        raise APIError(
            "The API answered successfully but the body was not JSON.",
            status=status,
            url=url,
            body=body,
        ) from exc


def _status_message(status: int) -> str:
    if status == httpx.codes.BAD_REQUEST:
        return (
            "The API rejected the request as malformed. Check identifiers for typos; "
            "an unknown property in a relation expression also causes this."
        )
    if status == httpx.codes.NOT_FOUND:
        return "No such endpoint on this deployment."
    if status == httpx.codes.METHOD_NOT_ALLOWED:
        return "This endpoint does not accept that HTTP method."
    if status >= httpx.codes.INTERNAL_SERVER_ERROR:
        return "The API failed while answering. Retrying later usually works."
    return "The API answered with an error."


def _sleep_before_retry(attempt: int, retry_after: str | None) -> None:
    delay = 0.5 * 2**attempt
    if retry_after is not None:
        # An HTTP-date Retry-After is ignored; the exponential delay is close enough.
        with contextlib.suppress(ValueError):
            delay = max(delay, float(retry_after))
    time.sleep(min(delay, 30.0))
