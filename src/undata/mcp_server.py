"""undata as an MCP connector: UN data for AI assistants such as Claude.

Run it with ``undata-mcp`` (``pip install "undata[mcp]"``). It speaks the Model
Context Protocol over stdio by default, for Claude Desktop, Claude Code and other
local clients, or over Streamable HTTP with ``--http``.

Every tool is read-only and wraps one undata function, so an assistant gets what a
person gets: UN names and M49 regions, the source and year on every value, gaps
named rather than counted as zero, and the analyses UN reports run (progress by the
UN Statistics Division's method, country profiles, gaps between groups). Data-quality
warnings come back as notes in the answer, so the assistant can repeat them. The
analysis tools can return their chart as an image.
"""

from __future__ import annotations

import argparse
import io
import json
import threading
import warnings
from collections.abc import Callable, Sequence
from typing import Annotated, Any, Final, Literal, TypeVar

import anyio
import pandas as pd
from mcp.server.mcpserver import Image, MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations
from pydantic import Field

from . import sdg
from .analysis import availability, benchmark, gap, profile, progress
from .breakdowns import breakdowns
from .data import change, compare, get, latest, totals
from .errors import UNDataError
from .export import cite
from .indicators import about, search
from .places import countries, regions
from .summary import describe, fmt_number

__all__ = ["main", "server"]

T = TypeVar("T")

INSTRUCTIONS: Final = """\
undata reads the UN System Data Commons (data.un.org): SDG indicators and other UN
statistics, by country, region and UN group. It is an unofficial client.

How to work:
1. Find the indicator. undata_search_indicators takes plain words; undata_browse_sdg
   walks goal > target > indicator > series. An SDG number such as "3.1.1" works as an
   indicator wherever one series reports it; when several do, the error lists their ids.
2. Fetch or analyse. Places are country names ("Viet Nam", "Côte d'Ivoire"), ISO3 codes,
   UN M49 regions ("Southern Asia", "Africa") or UN groups ("LDCs", "LLDCs", "SIDS").
   "World" and groups work in undata_group_totals and undata_benchmark_groups.
3. Answer with care. Give the year with every value: countries' latest years differ.
   Missing data is not zero. Repeat the notes each answer carries. Cite the source
   lines given. Progress statuses follow the UN Statistics Division's published method;
   name it when you use them.
"""

#: Columns that identify rather than inform; left out of answers to keep them short.
_HIDDEN: Final = frozenset({"iso3", "indicator", "source_url", "facet", "m49"})
#: Rows shown in one answer before it says how many more there are.
_MAX_ROWS: Final = 300
#: Charts are sent at this resolution: sharp on screen, small enough for a chat.
_CHART_DPI: Final = 144

READ_ONLY: Final = ToolAnnotations(
    read_only_hint=True, destructive_hint=False, idempotent_hint=True, open_world_hint=True
)

# undata keeps session state and matplotlib keeps global settings, and warnings are
# captured process-wide; one tool runs at a time.
_LOCK = threading.Lock()

Places = Annotated[
    list[str],
    Field(
        min_length=1,
        description='Countries, regions or groups, e.g. ["Chad", "Niger"], ["Southern Asia"], ["LDCs"].',
    ),
]
Indicator = Annotated[
    str,
    Field(
        min_length=1,
        description='An indicator id from undata_search_indicators, or an SDG number such as "3.1.1".',
    ),
]
Indicators = Annotated[
    list[str],
    Field(min_length=1, max_length=10, description="One or more indicator ids or SDG numbers."),
]
Format = Annotated[
    Literal["markdown", "json"],
    Field(description='"markdown" to read, "json" for exact values to compute with.'),
]
WithChart = Annotated[
    bool, Field(description="Also return a publication-ready chart of the result, as an image.")
]
Within = Annotated[
    int | None,
    Field(ge=1, le=50, description="Only values from the past N years; older ones are named."),
]

server: MCPServer = MCPServer(
    "undata_mcp",
    title="UN data (undata)",
    instructions=INSTRUCTIONS,
    website_url="https://nerd-factory.github.io/undata/",
    log_level="WARNING",  # stderr stays quiet: one line per data request is noise in a client log
)


def _tool(name: str, title: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Register a read-only tool whose answer is text, sometimes with an image."""
    return server.tool(name=name, title=title, annotations=READ_ONLY, structured_output=False)


# ── Running undata safely ────────────────────────────────────────────────


async def _call(fn: Callable[[], T]) -> tuple[T, list[str]]:
    """Run ``fn`` in a worker thread; return its result and any undata warnings as notes."""

    def guarded() -> tuple[T, list[str]]:
        with _LOCK, warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            try:
                result = fn()
            except (UNDataError, ValueError, KeyError) as exc:
                raise ToolError(_message(exc)) from exc
        notes = list(dict.fromkeys(str(w.message) for w in caught if _ours(w.category)))
        return result, notes

    return await anyio.to_thread.run_sync(guarded)


def _ours(category: type[Warning]) -> bool:
    from .errors import UNDataWarning  # noqa: PLC0415 — keeps the import list short above

    return issubclass(category, UNDataWarning)


#: The Python calls undata's messages suggest, and the tool that does the same here.
_HINTS: Final = (
    ("un.search(", "undata_search_indicators("),
    ("un.sdg.series(", "undata_browse_sdg("),
    ("un.countries() or un.regions()", "undata_list_places"),
    ("un.countries()", "undata_list_places"),
    ("un.regions()", "undata_list_places"),
    ("un.breakdowns()", "undata_describe_indicator"),
)


def _message(exc: BaseException) -> str:
    text = str(exc.args[0]) if isinstance(exc, KeyError) and exc.args else str(exc)
    for call, tool in _HINTS:
        text = text.replace(call, tool)
    return text


# ── Shaping answers ──────────────────────────────────────────────────────


def _cell(value: Any) -> str:
    if value is None or (not isinstance(value, str | list | tuple) and pd.isna(value)):
        return ""
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, float):
        return str(int(value)) if value.is_integer() and abs(value) < 1e15 else fmt_number(value)  # noqa: PLR2004
    return str(value).replace("|", "/").replace("\n", " ")


def _compact(table: pd.DataFrame, *, ids: bool = False) -> tuple[pd.DataFrame, dict[str, str]]:
    """Drop id columns (unless ``ids``); lift columns with one value for every row to a header."""
    frame = (
        table.reset_index() if table.index.name or isinstance(table.index, pd.MultiIndex) else table
    )
    hidden = _HIDDEN - {"indicator"} if ids else _HIDDEN
    frame = frame.drop(columns=[c for c in frame.columns if c in hidden])
    header: dict[str, str] = {}
    if len(frame) > 1:
        for column in ("indicator_name", "unit", "source"):
            if column in frame.columns and frame[column].nunique(dropna=False) == 1:
                header[column] = _cell(frame[column].iloc[0])
                frame = frame.drop(columns=column)
    return frame, header


def _markdown(frame: pd.DataFrame) -> str:
    if frame.empty:
        return "_No rows._"
    columns = [str(c) for c in frame.columns]
    lines = ["| " + " | ".join(columns) + " |", "|" + "---|" * len(columns)]
    lines += [
        "| " + " | ".join(_cell(v) for v in row) + " |" for row in frame.itertuples(index=False)
    ]
    return "\n".join(lines)


def _records(frame: pd.DataFrame) -> list[dict[str, Any]]:
    clean = frame.astype(object).where(pd.notna(frame), None)
    return [{str(k): v for k, v in row.items()} for row in clean.to_dict(orient="records")]


def _sources(table: pd.DataFrame) -> str:
    try:
        return cite(table)
    except (ValueError, KeyError):
        return ""


def _summary(table: pd.DataFrame) -> str:
    try:
        return describe(table)
    except (ValueError, KeyError, TypeError):
        return ""


def _answer(
    table: pd.DataFrame,
    notes: Sequence[str],
    *,
    title: str,
    response_format: str,
    offset: int = 0,
    limit: int = _MAX_ROWS,
    summary: bool = True,
    ids: bool = False,
) -> str:
    """One table as a reply: header, rows (paged), summary, notes and sources."""
    frame, header = _compact(table, ids=ids)
    total = len(frame)
    page = frame.iloc[offset : offset + limit]
    more = offset + len(page) < total
    sentence = _summary(table) if summary else ""
    sources = _sources(table)
    if response_format == "json":
        return json.dumps(
            {
                "title": title,
                **header,
                "total_rows": total,
                "offset": offset,
                "rows": _records(page),
                "has_more": more,
                "next_offset": offset + len(page) if more else None,
                "summary": sentence or None,
                "notes": list(notes),
                "sources": sources or None,
            },
            ensure_ascii=False,
            default=str,
        )
    parts = [f"## {title}"]
    parts += [f"**{key.replace('_', ' ').capitalize()}:** {value}" for key, value in header.items()]
    parts.append(_markdown(page))
    if more:
        parts.append(
            f"_Rows {offset + 1}-{offset + len(page)} of {total}. Ask again with "
            f"offset={offset + len(page)} for more._"
        )
    if sentence:
        parts.append(f"**Summary:** {sentence}")
    if notes:
        parts.append("**Notes:**\n" + "\n".join(f"- {note}" for note in notes))
    if sources:
        parts.append(f"**Sources:**\n{sources}")
    return "\n\n".join(parts)


async def _with_chart(
    text: str, table: pd.DataFrame, wanted: bool, kind: str = "auto"
) -> str | list[Any]:
    """``text``, plus the chart as an image when ``wanted`` and it can be drawn."""
    if not wanted:
        return text

    def draw() -> bytes:
        from .chart import chart  # noqa: PLC0415 — matplotlib is loaded only when asked

        figure = chart(table, kind=kind)  # type: ignore[arg-type]
        buffer = io.BytesIO()
        figure.savefig(buffer, format="png", dpi=_CHART_DPI, bbox_inches="tight", facecolor="white")
        return buffer.getvalue()

    try:
        png, _ = await _call(draw)
    except ToolError as exc:
        return f"{text}\n\n_No chart: {exc}_"
    return [text, Image(data=png, format="png")]


# ── Finding indicators and places ────────────────────────────────────────


@_tool("undata_search_indicators", "Search UN indicators")
async def search_indicators(
    query: Annotated[
        str, Field(min_length=2, description='Plain words, e.g. "maternal mortality".')
    ],
    limit: Annotated[int, Field(ge=1, le=50, description="Most indicators to return.")] = 10,
    all_sources: Annotated[
        bool, Field(description="Include copies of the same series held under other sources.")
    ] = False,
    response_format: Format = "markdown",
) -> str:
    """Find indicators by what they measure.

    Returns one row per indicator: its id (pass it to the other tools), name, source,
    how many places and years have data, and its SDG number if it has one. Start here
    when you do not know an indicator's id.
    """
    table, notes = await _call(lambda: search(query, all_sources=all_sources, limit=limit))
    return _answer(
        table,
        notes,
        title=f'Indicators matching "{query}"',
        response_format=response_format,
        summary=False,
        ids=True,
    )


@_tool("undata_describe_indicator", "Describe an indicator")
async def describe_indicator(indicator: Indicator) -> str:
    """What an indicator measures, whose it is, its unit, its years, and its breakdowns.

    Breakdowns (by sex, age, urbanization, wealth...) are what undata_get_data's
    ``breakdown`` and undata_group_gap's ``breakdown`` accept.
    """
    info, notes = await _call(lambda: about(indicator))
    parts = [repr(info)]
    try:
        kinds, _ = await _call(lambda: breakdowns(indicator))
    except ToolError:
        kinds = pd.DataFrame()
    dimensions = [c for c in kinds.columns if c not in ("indicator", "name")]
    if dimensions:
        lines = [
            f"- {dim}: " + "; ".join(sorted(str(v) for v in kinds[dim].dropna().unique()))
            for dim in dimensions
        ]
        parts.append(
            f"Breakdowns ({len(kinds)} series in this family; pass a breakdown's name to "
            "undata_get_data or undata_group_gap):\n" + "\n".join(lines)
        )
    parts += [f"Note: {note}" for note in notes]
    return "\n\n".join(parts)


@_tool("undata_browse_sdg", "Browse the SDG framework")
async def browse_sdg(
    code: Annotated[
        str | None,
        Field(
            description='Empty for the 17 goals; a goal ("5") for its targets; a target ("5.5") '
            'for its indicators; an indicator ("5.5.1") for the series that report it.'
        ),
    ] = None,
) -> str:
    """Walk the SDG framework from goals down to series you can fetch."""
    depth = 0 if not code else code.count(".") + 1
    steps: dict[int, tuple[str, Callable[[], pd.DataFrame]]] = {
        0: ("The 17 Sustainable Development Goals", sdg.goals),
        1: (f"Targets of Goal {code}", lambda: sdg.targets(str(code))),
        2: (f"Indicators of Target {code}", lambda: sdg.indicators(str(code))),
        3: (f"Series reporting SDG indicator {code}", lambda: sdg.series(str(code))),
    }
    if depth not in steps:
        raise ToolError(
            f'"{code}" is not a goal, target or indicator number such as "5", "5.5" or "5.5.1".'
        )
    title, fetch = steps[depth]
    table, notes = await _call(fetch)
    return _answer(table, notes, title=title, response_format="markdown", summary=False, ids=True)


@_tool("undata_list_places", "List countries, regions and groups")
async def list_places(
    region: Annotated[
        str | None,
        Field(
            description='A region or group ("Western Africa", "LDCs"); empty to list every region and group.'
        ),
    ] = None,
) -> str:
    """Countries in a UN M49 region or UN group, or the list of regions and groups.

    Names are the UN's official names. LDCs, LLDCs and SIDS are the UN's current lists.
    """
    if region:
        table, notes = await _call(lambda: countries(region))
        return _answer(
            table,
            notes,
            title=f"Countries and areas in {region}",
            response_format="markdown",
            summary=False,
        )
    table, notes = await _call(regions)
    return _answer(
        table,
        notes,
        title="UN M49 regions and UN groups",
        response_format="markdown",
        summary=False,
    )


# ── Fetching data ────────────────────────────────────────────────────────


@_tool("undata_get_data", "Get data by year")
async def get_data(
    indicators: Indicators,
    places: Places,
    start_year: Annotated[int | None, Field(ge=1900, le=2100, description="First year.")] = None,
    end_year: Annotated[int | None, Field(ge=1900, le=2100, description="Last year.")] = None,
    breakdown: Annotated[
        str | None,
        Field(description='A breakdown such as "sex" or "age" (see undata_describe_indicator).'),
    ] = None,
    limit: Annotated[int, Field(ge=1, le=1000, description="Rows per page.")] = 200,
    offset: Annotated[int, Field(ge=0, description="Rows to skip, for the next page.")] = 0,
    response_format: Format = "markdown",
) -> str:
    """Values by country and year, with unit and source on every row."""
    years = (
        None
        if start_year is None and end_year is None
        else range(start_year or 1900, (end_year or 2100) + 1)
    )
    table, notes = await _call(lambda: get(indicators, places, years, by=breakdown))
    return _answer(
        table, notes, title="Data", response_format=response_format, offset=offset, limit=limit
    )


@_tool("undata_latest_values", "Latest value per country")
async def latest_values(
    indicators: Indicators,
    places: Places,
    within_years: Within = None,
    include_chart: WithChart = False,
    response_format: Format = "markdown",
) -> str | list[Any]:
    """Each country's most recent value, with the year it is from.

    Countries' latest years differ; the notes say so. ``within_years`` drops values
    older than that and names the countries left out.
    """
    table, notes = await _call(lambda: latest(indicators, places, within=within_years))
    text = _answer(table, notes, title="Latest values", response_format=response_format)
    return await _with_chart(text, table, include_chart and len(indicators) == 1)


@_tool("undata_group_totals", "Official totals for regions and groups")
async def group_totals(
    indicators: Indicators,
    places: Annotated[
        list[str],
        Field(
            min_length=1,
            description='Regions or groups, e.g. ["World", "LDCs", "Sub-Saharan Africa"].',
        ),
    ],
    latest_only: Annotated[bool, Field(description="Only each place's latest value.")] = True,
    response_format: Format = "markdown",
) -> str:
    """The figure the agency published for a region, a UN group or the world.

    These are official aggregates, not averages of countries.
    """
    table, notes = await _call(lambda: totals(indicators, places, latest=latest_only))
    return _answer(table, notes, title="Published totals", response_format=response_format)


@_tool("undata_change_over_time", "Change between two years")
async def change_over_time(
    indicator: Indicator,
    places: Places,
    start_year: Annotated[int, Field(ge=1900, le=2100)],
    end_year: Annotated[int, Field(ge=1900, le=2100)],
    include_chart: WithChart = False,
    response_format: Format = "markdown",
) -> str | list[Any]:
    """Each country's value in two years, the difference and the percentage change."""
    table, notes = await _call(lambda: change(indicator, places, start_year, end_year))
    text = _answer(
        table, notes, title=f"Change {start_year} to {end_year}", response_format=response_format
    )
    return await _with_chart(text, table, include_chart)


@_tool("undata_compare_indicators", "Compare indicators side by side")
async def compare_indicators(
    indicators: Annotated[
        list[str], Field(min_length=2, max_length=6, description="Two or more indicators.")
    ],
    places: Places,
    within_years: Within = None,
    include_chart: WithChart = False,
    response_format: Format = "markdown",
) -> str | list[Any]:
    """Latest values of several indicators side by side, with who has which spelled out.

    With exactly two indicators, the chart is a scatter of one against the other.
    """
    table, notes = await _call(lambda: compare(indicators, places, within=within_years))
    text = _answer(table, notes, title="Comparison", response_format=response_format)
    return await _with_chart(text, table, include_chart and len(indicators) == 2)  # noqa: PLR2004


# ── Analyses ─────────────────────────────────────────────────────────────


@_tool("undata_assess_progress", "Assess SDG progress")
async def assess_progress(
    indicator: Indicator,
    places: Places,
    better: Annotated[
        Literal["higher", "lower"],
        Field(
            description='"lower" when a fall is progress (mortality, poverty); "higher" otherwise.'
        ),
    ],
    target: Annotated[
        float | None, Field(description="The value to reach by target_year, e.g. 70 for SDG 3.1.1.")
    ] = None,
    baseline_year: Annotated[int, Field(ge=1990, le=2030)] = 2015,
    target_year: Annotated[int, Field(ge=2020, le=2100)] = 2030,
    include_chart: WithChart = False,
    response_format: Format = "markdown",
) -> str | list[Any]:
    """Is each country on track? The UN Statistics Division's progress method.

    Each country's growth rate since the baseline is projected to the target year. With a
    target, the projected change is compared with the change the target needs; without,
    the growth rate is scored. Each country gets one of the SDG Report's categories, from
    "On track or target met" to "Regression", and a 0-5 score.
    """
    table, notes = await _call(
        lambda: progress(
            indicator,
            places,
            better=better,
            target=target,
            baseline=baseline_year,
            target_year=target_year,
        )
    )
    text = _answer(table, notes, title="Progress assessment", response_format=response_format)
    return await _with_chart(text, table, include_chart)


@_tool("undata_country_profile", "Country profile")
async def country_profile(
    country: Annotated[str, Field(min_length=2, description='One country, e.g. "Chad".')],
    indicators: Indicators,
    include_chart: WithChart = False,
    response_format: Format = "markdown",
) -> str | list[Any]:
    """One country's latest values beside its UN M49 region and the world, with its rank."""
    table, notes = await _call(lambda: profile(country, indicators))
    text = _answer(table, notes, title=f"Profile of {country}", response_format=response_format)
    return await _with_chart(text, table, include_chart)


@_tool("undata_group_gap", "Gap between two groups")
async def group_gap(
    indicator: Indicator,
    places: Places,
    breakdown: Annotated[
        str,
        Field(description='"sex", "urbanization", "wealth quantile", or another breakdown it has.'),
    ] = "sex",
    groups: Annotated[
        list[str] | None,
        Field(
            min_length=2,
            max_length=2,
            description='The two groups, e.g. ["Rural", "Urban"]; default depends on the breakdown.',
        ),
    ] = None,
    include_chart: WithChart = False,
    response_format: Format = "markdown",
) -> str | list[Any]:
    """Two groups compared in the latest year that has both: the values, ratio and difference.

    For example women and men, rural and urban, or the poorest and richest fifth.
    """
    pair = (groups[0], groups[1]) if groups else None
    table, notes = await _call(lambda: gap(indicator, places, by=breakdown, groups=pair))
    text = _answer(table, notes, title=f"Gap by {breakdown}", response_format=response_format)
    return await _with_chart(text, table, include_chart)


@_tool("undata_benchmark_groups", "UN groups side by side")
async def benchmark_groups(
    indicator: Indicator,
    places: Annotated[
        list[str], Field(min_length=1, description="Regions or groups to compare.")
    ] = ["World", "LDCs", "LLDCs", "SIDS"],  # noqa: B006 — pydantic copies the default
    baseline_year: Annotated[int, Field(ge=1990, le=2030)] = 2015,
    include_chart: WithChart = False,
    response_format: Format = "markdown",
) -> str | list[Any]:
    """Published totals for regions and UN groups, at the baseline year and the latest."""
    table, notes = await _call(lambda: benchmark(indicator, places, baseline=baseline_year))
    text = _answer(table, notes, title="Benchmark", response_format=response_format)
    return await _with_chart(text, table, include_chart)


@_tool("undata_check_availability", "Who reports what")
async def check_availability(
    indicators: Indicators,
    places: Places,
    within_years: Within = None,
    include_chart: WithChart = False,
    response_format: Format = "markdown",
) -> str | list[Any]:
    """The year of each country's latest value for each indicator; blank means no data.

    Run this before comparing countries, to see whether their data is comparable in time.
    """
    table, notes = await _call(lambda: availability(indicators, places, within=within_years))
    text = _answer(
        table,
        notes,
        title="Data availability (year of latest value)",
        response_format=response_format,
        summary=False,
    )
    return await _with_chart(text, table, include_chart)


# ── Running the server ───────────────────────────────────────────────────


def main(argv: Sequence[str] | None = None) -> None:
    """Start the connector: ``undata-mcp`` for stdio, ``undata-mcp --http`` for HTTP."""
    parser = argparse.ArgumentParser(prog="undata-mcp", description=__doc__.splitlines()[0])
    parser.add_argument(
        "--http", action="store_true", help="serve Streamable HTTP instead of stdio"
    )
    parser.add_argument("--host", default="127.0.0.1", help="HTTP host (default 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8000, help="HTTP port (default 8000)")
    parser.add_argument("--no-cache", action="store_true", help="do not keep responses on disk")
    args = parser.parse_args(argv)

    from ._session import configure  # noqa: PLC0415

    configure(cache=not args.no_cache)
    if args.http:
        server.run(  # pragma: no cover - serves until stopped
            "streamable-http",
            host=args.host,
            port=args.port,
            stateless_http=True,
            json_response=True,
        )
    else:
        server.run("stdio")  # pragma: no cover - serves until stdin closes
