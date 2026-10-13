"""Keep a table's row-per-value form beside it, in ``.attrs``, without upsetting pandas.

Wide, change, compare and analysis tables carry the long table they came from, so
:func:`undata.cite`, :func:`undata.save` and :func:`undata.chart` still know every
source. pandas compares and deep-copies ``.attrs`` on ``concat`` and most other
operations; a bare DataFrame there makes ``pd.concat`` fail ("truth value of a
DataFrame is ambiguous") and copies the whole long table on every step. The small
holder below compares by content and is shared, not copied.
"""

from __future__ import annotations

from typing import Any

import pandas as pd


class Kept:
    """A long table attached to another table."""

    __slots__ = ("frame",)
    __hash__ = None  # type: ignore[assignment]

    def __init__(self, frame: pd.DataFrame) -> None:
        self.frame = frame

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Kept) and (
            other.frame is self.frame or other.frame.equals(self.frame)
        )

    def __deepcopy__(self, memo: dict[int, Any]) -> Kept:
        return self  # never changed in place, so every copy can share it

    def __repr__(self) -> str:
        return f"<long table, {len(self.frame)} rows>"


def keep(table: pd.DataFrame, long: pd.DataFrame) -> pd.DataFrame:
    """Attach ``long`` to ``table`` and return ``table``."""
    table.attrs["long"] = Kept(long)
    return table


def long_of(table: pd.DataFrame) -> pd.DataFrame:
    """The long table attached to ``table``, or ``table`` itself."""
    kept = table.attrs.get("long")
    if isinstance(kept, Kept):
        return kept.frame
    return kept if isinstance(kept, pd.DataFrame) else table
