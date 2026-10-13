"""Saving a table, citing where it came from, and handing it to other tools.

* :func:`save` - Excel or CSV, with sources.
* :func:`cite` - citations for a report.
* :func:`for_ai` - the table with its sources and caveats, to paste into an AI assistant.
* :func:`ai_pack` - the same as files (data, metadata, prompt) to upload to one.
* :func:`powerquery` - Power Query (M) code, to get the same data in Power BI or Excel.
"""

from __future__ import annotations

import json
import zipfile
from collections.abc import Iterable, Mapping, Sequence
from datetime import date
from pathlib import Path
from typing import Final

import pandas as pd

from ._http import DEFAULT_BASE_URL
from .data import Years, _year_filter
from .indicators import check
from .places import expand
from .summary import coverage

__all__ = ["AI_TASKS", "ai_pack", "cite", "for_ai", "powerquery", "save"]

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
            if {"indicator_name", "country", "year"} <= set(_long(table).columns):
                coverage(table).to_excel(writer, sheet_name="coverage", index=False)
    else:
        raise ValueError(f"Cannot save to {target.name!r}. Use a name ending in .xlsx or .csv.")
    return target


#: What to ask an assistant, by task. Each keeps it to the numbers it was given.
AI_TASKS: Final[Mapping[str, str]] = {
    "explain": "Explain what this table shows, in plain language, for a reader with no "
    "statistics background. Point out the highest and lowest values and the years.",
    "brief": "Draft a briefing paragraph of about 150 words from this table, for a UN "
    "report. Quote numbers with their year and source. Mention any countries without data.",
    "trends": "Describe how the values changed over time, country by country. Say which "
    "rose, which fell, and by how much, with the years. Do not extrapolate.",
    "gaps": "List what this table cannot tell us: countries without data, values that are "
    "old, and comparisons across different years. Suggest what to check before publishing.",
    "chart": "Suggest the one chart that best shows this table, and say why. Name what goes "
    "on each axis and what to highlight. Do not invent values to fill gaps.",
}

_RULES: Final = [
    "- Use only the numbers in this data. Do not add figures from memory or the web.",
    "- Name the source when you quote a number, and give its year.",
    "- A place missing from the data has no data. It is not zero.",
    "- Values from different years are not directly comparable; say which year each is.",
    "- If the data cannot answer the question, say so rather than estimating.",
]


def _markdown(frame: pd.DataFrame) -> str:
    """A Markdown table, with no dependency beyond pandas."""
    keep_index = not isinstance(frame.index, pd.RangeIndex)
    data = frame.reset_index() if keep_index else frame

    def cell(value: object) -> str:
        if value is None or (isinstance(value, float) and pd.isna(value)) or value is pd.NA:
            return ""
        return str(value).replace("|", "\\|").replace("\n", " ")

    header = "| " + " | ".join(str(c) for c in data.columns) + " |"
    rule = "|" + "|".join("---" for _ in data.columns) + "|"
    rows = ["| " + " | ".join(cell(v) for v in row) + " |" for row in data.itertuples(index=False)]
    return "\n".join([header, rule, *rows])


def _window_lines(table: pd.DataFrame) -> list[str]:
    window = table.attrs.get("window") or {}
    if window.get("since") is None:
        return []
    span = (
        f"the last {window['within_years']} years ({window['since']}-{window['until']})"
        if window.get("within_years") is not None
        else f"{window['since']} or later"
    )
    lines = [f"- Each value is the place's latest from {span}."]
    stale = table.attrs.get("stale") or []
    if stale:
        old = ", ".join(f"{s['country']} ({s['year']})" for s in stale)
        lines.append(f"- Left out as too old: {old}.")
    return lines


def _gaps(table: pd.DataFrame) -> list[str]:
    missing = table.attrs.get("missing") or []
    if not missing:
        return []
    names = sorted({m["country"] for m in missing})
    return [f"No data for: {', '.join(names)}."]


def _citations(table: pd.DataFrame) -> list[str]:
    try:
        lines = cite(table).splitlines()
    except ValueError:
        return []
    return ["Sources:", *[f"- {line}" for line in lines]] if lines else []


def for_ai(
    table: pd.DataFrame,
    *,
    task: str | None = None,
    question: str | None = None,
    max_rows: int = 200,
) -> str:
    """Format a table for an AI assistant, with its sources, caveats and a task.

    Paste the result into Copilot, ChatGPT or Claude. It tells the assistant to use
    only these numbers, to name the source and year, and that a missing country has
    no data rather than a value of zero. Asking an assistant what a statistic *is*
    invites a made-up number; giving it the statistic and asking what it *means*
    does not.

    Args:
        table: A table from :func:`undata.get`, :func:`undata.latest`,
            :func:`undata.totals`, :func:`undata.change` or :func:`undata.wide`.
        task: What to ask for: ``"explain"``, ``"brief"``, ``"trends"``, ``"gaps"`` or
            ``"chart"``. Leave it out to ask your own question afterwards.
        question: Your own question, added after the data.
        max_rows: Rows beyond this are cut, and the cut is stated.

    Returns:
        Markdown text, ready to paste.

    Example:
        >>> import undata as un
        >>> print(un.for_ai(un.latest("3.1.1", "Southern Asia"), task="brief"))  # doctest: +SKIP
    """
    if task is not None and task not in AI_TASKS:
        raise ValueError(f"Unknown task {task!r}. Choose one of: {', '.join(AI_TASKS)}.")
    retrieved = table.attrs.get("retrieved") or date.today().isoformat()
    parts = [
        f"# Data from the UN System Data Commons (data.un.org), retrieved {retrieved}",
        "",
        "Rules for the assistant:",
        *_RULES,
        *_window_lines(table),
        "",
        _markdown(table.head(max_rows)),
    ]
    if len(table) > max_rows:
        parts.append(f"\n(Showing {max_rows} of {len(table)} rows.)")
    for block in (_gaps(table), _citations(table)):
        if block:
            parts += ["", *block]
    if task is not None:
        parts += ["", f"Task: {AI_TASKS[task]}"]
    if question:
        parts += ["", f"Question: {question}"]
    return "\n".join(parts)


def _data_dictionary(table: pd.DataFrame) -> list[str]:
    meanings = {
        "country": "Country, region or group, by its UN name.",
        "iso3": "ISO 3166 three-letter code. Empty for regions and groups.",
        "year": "The year the value refers to.",
        "value": "The value, in the unit given.",
        "unit": "The unit of measure.",
        "indicator_name": "What the indicator measures.",
        "indicator": "The indicator's id on the UN System Data Commons.",
        "source": "The organization that produced the figure.",
        "source_url": "Where that organization publishes it.",
    }
    columns = list(_long(table).columns)
    return [f"- `{c}`: {meanings.get(c, 'See the column name.')}" for c in columns]


def ai_pack(table: pd.DataFrame, path: str | Path, *, task: str | None = None) -> Path:
    """Write a data pack to upload to an AI assistant: the data, what it means, a prompt.

    Upload the pack (or its three files) to ChatGPT, Claude or Copilot, then paste
    ``prompt.md`` as your message. The assistant gets the numbers as data rather than
    pasted text, so it can calculate with them, and the metadata keeps it honest about
    units, sources, years and gaps.

    The pack holds:

    * ``data.csv`` - one row per value, with unit and source on every row.
    * ``metadata.md`` - what each column means, each indicator's unit, source and
      citation, how complete the data is, and the caveats.
    * ``prompt.md`` - rules for the assistant, and a task or suggested questions.

    Args:
        table: A table from :func:`undata.get`, :func:`undata.latest`,
            :func:`undata.totals`, :func:`undata.change` or :func:`undata.wide`.
        path: A ``.zip`` file, or a folder to write the three files into.
        task: As for :func:`for_ai`. Left out, the prompt lists questions to choose from.

    Returns:
        The path written.

    Example:
        >>> import undata as un
        >>> un.ai_pack(un.latest("3.1.1", "LDCs", within=10), "maternal-mortality.zip")  # doctest: +SKIP
    """
    if task is not None and task not in AI_TASKS:
        raise ValueError(f"Unknown task {task!r}. Choose one of: {', '.join(AI_TASKS)}.")
    long = _long(table)
    retrieved = table.attrs.get("retrieved") or date.today().isoformat()
    metadata = [
        "# About this data",
        "",
        f"Retrieved {retrieved} from the {_PLATFORM}, with undata "
        "(https://pypi.org/project/undata/). Unofficial; the data belongs to the agencies "
        "that publish it.",
        "",
        "## Columns in data.csv",
        "",
        *_data_dictionary(table),
    ]
    if {"indicator_name", "indicator", "source"} <= set(long.columns):
        indicators = long.drop_duplicates(["indicator", "source"])
        metadata += ["", "## Indicators", ""]
        for row in indicators.itertuples(index=False):
            unit = getattr(row, "unit", "") or "not stated"
            metadata += [
                f"### {row.indicator_name}",
                "",
                f"- Id: `{row.indicator}`",
                f"- Unit: {unit}",
                f"- Source: {row.source} ({getattr(row, 'source_url', '') or 'no link'})",
                "",
            ]
    if {"indicator_name", "country", "year"} <= set(long.columns):
        metadata += ["## How complete it is", "", _markdown(coverage(table)), ""]
    caveats = [*_window_lines(table), *[f"- {g}" for g in _gaps(table)]]
    if caveats:
        metadata += ["## Caveats", "", *caveats, ""]
    citations = _citations(table)
    if citations:
        metadata += ["## How to cite", "", *citations[1:], ""]

    ask = (
        [f"Task: {AI_TASKS[task]}"]
        if task
        else ["Choose a task, or ask your own question:", *[f"- {t}" for t in AI_TASKS.values()]]
    )
    prompt = [
        "I have attached data.csv and metadata.md, from the UN System Data Commons.",
        "Read metadata.md first: it says what each column means and what the data cannot show.",
        "",
        "Rules:",
        *_RULES,
        "",
        *ask,
    ]
    files = {
        "data.csv": long.to_csv(index=False),
        "metadata.md": "\n".join(metadata),
        "prompt.md": "\n".join(prompt) + "\n",
    }
    target = Path(path)
    if target.suffix.lower() == ".zip":
        with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for name, content in files.items():
                archive.writestr(name, content)
    else:
        target.mkdir(parents=True, exist_ok=True)
        for name, content in files.items():
            (target / name).write_text(content, encoding="utf-8")
    return target


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
