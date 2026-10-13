"""Saving a table and citing where it came from."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd

__all__ = ["cite", "save"]

_PLATFORM = "UN System Data Commons, https://data.un.org"


def _sources(table: pd.DataFrame) -> pd.DataFrame:
    needed = {"indicator", "indicator_name", "source", "source_url"}
    if not needed <= set(table.columns):
        raise ValueError(
            "This table has no source columns. cite() and save() work on tables from "
            "un.get() or un.latest()."
        )
    return (
        table[["indicator_name", "indicator", "source", "source_url"]]
        .drop_duplicates()
        .sort_values(["indicator_name", "source"], ignore_index=True)
    )


def cite(table: pd.DataFrame) -> str:
    """Write a citation for every indicator and source in a table.

    Credit goes to the agency that produced the data, with the platform as where it
    was retrieved.

    Args:
        table: A table from :func:`undata.get` or :func:`undata.latest`.

    Returns:
        One citation per line. Print it, or paste it under a chart.

    Example:
        >>> import undata as un
        >>> print(un.cite(table))  # doctest: +SKIP
        SDG Global Database. Maternal mortality ratio [Sex=Female] ...
    """
    retrieved = table.attrs.get("retrieved") or date.today().isoformat()
    lines = []
    for row in _sources(table).itertuples(index=False):
        url = f" {row.source_url}." if isinstance(row.source_url, str) and row.source_url else ""
        lines.append(
            f"{row.source}. {row.indicator_name} ({row.indicator}).{url} "
            f"Retrieved {retrieved} from the {_PLATFORM}."
        )
    return "\n".join(lines)


def save(table: pd.DataFrame, path: str | Path) -> Path:
    """Save a table to Excel or CSV, with its sources.

    An ``.xlsx`` file gets two sheets: ``data``, and ``sources`` with a citation for
    each indicator and the list of countries that had no data. A ``.csv`` file holds
    the data; every row already carries its source.

    Args:
        table: A table from :func:`undata.get` or :func:`undata.latest`.
        path: Where to save it, ending in ``.xlsx`` or ``.csv``.

    Returns:
        The path written.

    Example:
        >>> import undata as un
        >>> un.save(table, "maternal-mortality.xlsx")  # doctest: +SKIP
    """
    target = Path(path)
    suffix = target.suffix.lower()
    if suffix == ".csv":
        table.to_csv(target, index=False)
    elif suffix == ".xlsx":
        sources = _sources(table)
        sources["citation"] = cite(table).splitlines()
        missing = pd.DataFrame(
            table.attrs.get("missing", []), columns=["country", "indicator_name"]
        )
        with pd.ExcelWriter(target) as writer:
            table.to_excel(writer, sheet_name="data", index=False)
            sources.to_excel(writer, sheet_name="sources", index=False)
            if not missing.empty:
                missing.to_excel(writer, sheet_name="no data", index=False)
    else:
        raise ValueError(f"Cannot save to {target.name!r}. Use a name ending in .xlsx or .csv.")
    return target
