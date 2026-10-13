"""The shared connection and in-memory cache behind the module-level functions.

Most people never touch this: ``un.get(...)`` opens a connection the first time it
is needed and reuses it. Call :func:`configure` to change the timeout or point at
another deployment.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, TypeVar

from ._http import DEFAULT_BASE_URL, DEFAULT_RETRIES, DEFAULT_TIMEOUT, Transport

T = TypeVar("T")


class _State:
    transport: Transport | None = None
    cache: dict[str, Any] = {}  # noqa: RUF012 — one process-wide cache, deliberately


def transport() -> Transport:
    """Return the shared transport, opening it on first use."""
    if _State.transport is None:
        _State.transport = Transport()
    return _State.transport


def configure(
    *,
    base_url: str = DEFAULT_BASE_URL,
    timeout: float = DEFAULT_TIMEOUT,
    retries: int = DEFAULT_RETRIES,
) -> None:
    """Change how undata connects, and forget anything it has cached.

    Args:
        base_url: Root of the Data Commons deployment.
        timeout: Seconds to wait for each response. Raise it on a slow connection.
        retries: How many times to retry a request that failed for a temporary reason.

    Example:
        >>> import undata as un
        >>> un.configure(timeout=60)
    """
    if _State.transport is not None:
        _State.transport.close()
    _State.transport = Transport(base_url=base_url, timeout=timeout, retries=retries)
    _State.cache.clear()


def cached(key: str, factory: Callable[[], T]) -> T:
    """Return the cached value for ``key``, computing it with ``factory`` the first time."""
    if key not in _State.cache:
        _State.cache[key] = factory()
    value: T = _State.cache[key]
    return value
