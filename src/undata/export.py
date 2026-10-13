"""Saving a table, citing where it came from, and handing it to other tools.

* :func:`save` - Excel or CSV, with sources.
* :func:`cite` - citations for a report.
* :func:`for_ai` - the table with its sources and caveats, to paste into an AI assistant.
* :func:`powerquery` - Power Query (M) code, to get the same data in Power BI or Excel.
"""

from __future__ import annotations

import importlib.util
import json
from collections.abc import Iterable, Sequence
from datetime import date
from pathlib import Path

import pandas as pd

from ._http import DEFAULT_BASE_URL
from .data import Years, _year_filter
from .indicators import check
from .places import expand

__all__ = ["cite", "for_ai", "powerquery", "save"]

_PLATFORM = "UN System Data Commons, https://data.un.org"


def _long(table: pd.DataFrame) -> pd.DataFrame:
    """The row-per-value table behind a wide, change or compare table."""
    long = table.attrs.get("long")
    return long if isinstance(long, pd.DataFrame) else table


def _sources(table: pd.DataFrame) -> pd.DataFrame:
    table = _long(table)
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
    keep_index = not isinstance(table.index, pd.RangeIndex)  # wide tables index by country
    if suffix == ".csv":
        table.to_csv(target, index=keep_index)
    elif suffix == ".xlsx":
        sources = _sources(table)
        sources["citation"] = cite(table).splitlines()
        missing = pd.DataFrame(
            table.attrs.get("missing", []), columns=["country", "indicator_name"]
        )
        with pd.ExcelWriter(target) as writer:
            table.to_excel(writer, sheet_name="data", index=keep_index)
            sources.to_excel(writer, sheet_name="sources", index=False)
            if not missing.empty:
                missing.to_excel(writer, sheet_name="no data", index=False)
    else:
        raise ValueError(f"Cannot save to {target.name!r}. Use a name ending in .xlsx or .csv.")
    return target


def for_ai(table: pd.DataFrame, *, max_rows: int = 200) -> str:
    """Format a table for an AI assistant, with its sources and caveats attached.

    Paste the result into Copilot, ChatGPT or Claude before asking your question. It
    tells the assistant to use only these numbers, to name the source, and that a
    missing country has no data rather than a value of zero. Asking an assistant
    what a statistic *is* invites a made-up number; giving it the statistic and
    asking what it *means* does not.

    Args:
        table: A table from :func:`undata.get`, :func:`undata.latest`,
            :func:`undata.totals`, :func:`undata.change` or :func:`undata.wide`.
        max_rows: Rows beyond this are cut, and the cut is stated.

    Returns:
        Markdown text.

    Example:
        >>> import undata as un
        >>> print(un.for_ai(un.latest("3.1.1", "Southern Asia")))  # doctest: +SKIP
    """
    retrieved = table.attrs.get("retrieved") or date.today().isoformat()
    shown = table.head(max_rows)
    keep_index = not isinstance(shown.index, pd.RangeIndex)
    body = (
        shown.to_markdown(index=keep_index) if _has_tabulate() else shown.to_csv(index=keep_index)
    )
    parts = [
        f"# Data from the UN System Data Commons (data.un.org), retrieved {retrieved}",
        "",
        "Instructions for the assistant:",
        "- Use only the numbers in this table. Do not add figures from memory.",
        "- Name the source when you quote a number.",
        "- A place missing from the table has no data. It is not zero.",
        "- Values from different years are not directly comparable; say which year.",
        "",
        body,
    ]
    if len(table) > max_rows:
        parts.append(f"\n(Showing {max_rows} of {len(table)} rows.)")
    missing = table.attrs.get("missing") or []
    if missing:
        names = sorted({m["country"] for m in missing})
        parts += ["", f"No data for: {', '.join(names)}."]
    try:
        citations = cite(table)
    except ValueError:
        citations = ""
    if citations:
        parts += ["", "Sources:", *[f"- {line}" for line in citations.splitlines()]]
    return "\n".join(parts)


def _has_tabulate() -> bool:
    """Whether the optional tabulate package is there; pandas needs it for Markdown."""
    return importlib.util.find_spec("tabulate") is not None


def powerquery(
    indicators: str | Sequence[str],
    countries: str | Iterable[str],
    years: Years = None,
) -> str:
    """Write Power Query (M) code that fetches the same data, for Power BI or Excel.

    In Power BI: Get data, Blank query, Advanced editor, then paste. In Excel: Data,
    Get Data, From Other Sources, Blank Query, Advanced Editor. The query refreshes
    on its own schedule after that, with no Python involved.

    Args:
        indicators: As for :func:`undata.get`.
        countries: As for :func:`undata.get`. Names are turned into ids now, so the
            query needs no lookups of its own.
        years: As for :func:`undata.get`.

    Returns:
        M code, ready to paste.

    Example:
        >>> import undata as un
        >>> print(un.powerquery("3.1.1", "Southern Asia", years=(2015, 2023)))  # doctest: +SKIP
    """
    names = check(indicators)
    places = expand(countries)
    keep = _year_filter(years)

    def m_list(items: Iterable[str]) -> str:
        return "{" + ", ".join(json.dumps(i) for i in items) + "}"

    def m_record(pairs: dict[str, str]) -> str:
        fields = ", ".join(f"#{json.dumps(k)} = {json.dumps(v)}" for k, v in pairs.items())
        return f"[{fields}]"

    year_filter = (
        f"    InYears    = Table.SelectRows(AddYear, each List.Contains({m_list(str(y) for y in sorted(keep))}, Text.From([year]))),\n"
        if keep
        else "    InYears    = AddYear,\n"
    )
    return f"""// Generated by undata (https://pypi.org/project/undata/).
// {", ".join(names.values())}
let
    Base      = {json.dumps(DEFAULT_BASE_URL)},
    Variables = {m_list(names)},
    Entities  = {m_list(p.id for p in places)},
    Names     = {m_record({p.id: p.name for p in places})},
    Indicator = {m_record(names)},

    // Base stays a literal and the path goes in RelativePath, so the Power BI
    // Service treats this as a fixed source and can refresh it on a schedule.
    Response = Json.Document(
        Web.Contents(Base, [
            RelativePath = "api/observations/series",
            Headers      = [#"Content-Type" = "application/json"],
            Content      = Json.FromValue([variables = Variables, entities = Entities])
        ])
    ),

    ByVariable = Table.RenameColumns(Record.ToTable(Response[data]), {{{{"Name", "indicator"}}}}),
    AddEntity  = Table.AddColumn(ByVariable, "entities", each Record.ToTable([Value])),
    DropRecord = Table.RemoveColumns(AddEntity, {{"Value"}}),
    ByEntity   = Table.ExpandTableColumn(DropRecord, "entities", {{"Name", "Value"}}, {{"id", "block"}}),
    AddObs     = Table.AddColumn(ByEntity, "obs",
                     each Table.FromRecords(Record.FieldOrDefault([block], "series", {{}}))),
    // A place with no observations is absent, not zero: drop it, never fill it with 0.
    HasData    = Table.SelectRows(AddObs, each Table.RowCount([obs]) > 0),
    DropBlock  = Table.RemoveColumns(HasData, {{"block"}}),
    Expanded   = Table.ExpandTableColumn(DropBlock, "obs", {{"date", "value"}}, {{"date", "value"}}),
    Typed      = Table.TransformColumnTypes(Expanded, {{{{"date", type text}}, {{"value", type number}}}}),
    AddYear    = Table.AddColumn(Typed, "year", each Int64.From(Text.Start([date], 4)), Int64.Type),
{year_filter}    AddCountry = Table.AddColumn(InYears, "country", each Record.FieldOrDefault(Names, [id], [id]), type text),
    AddName    = Table.AddColumn(AddCountry, "indicator_name",
                     each Record.FieldOrDefault(Indicator, [indicator], [indicator]), type text),
    Result     = Table.SelectColumns(AddName, {{"country", "year", "value", "indicator_name", "indicator", "id"}})
in
    Result
"""
