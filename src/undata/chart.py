"""Production-quality charts, chosen from the table you have.

:func:`chart` looks at the table and draws the chart that fits it:

====================================  ===========================================
table from                            chart
====================================  ===========================================
``latest``, ``totals``                ranked bars, with benchmark lines if asked
``get`` with several years            lines (up to six countries), else small multiples
``change``, ``trend``, ``benchmark``  dumbbell: start and end, per country
``progress``                          progress chart: status, path and target
``gap``                               paired dots, one per group
``availability``                      heatmap of how recent each value is
``profile``                           one row per indicator: country, region, world
``compare`` (two indicators)          labelled scatter
any one-value-per-country table       ``kind="map"``: a tile map, one square each
====================================  ===========================================

Every chart carries a title, a subtitle with the unit, and a caption with the
source, the retrieval date and the places that had no data. They export at print
quality: PNG at 300 dpi, or SVG and PDF with editable text.

Rules kept whatever the data: one indicator per value axis, never two scales;
missing countries listed, never drawn as zero; colour never the only way to tell
things apart. It needs matplotlib: ``pip install "undata[charts]"``. With
``interactive=True`` it draws an interactive Plotly chart instead (``pip install
plotly``).
"""

from __future__ import annotations

import csv
import textwrap
import warnings
from collections.abc import Callable, Sequence
from datetime import date
from functools import cache
from importlib import resources
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

import pandas as pd

from ._long import long_of
from .analysis import ordinal
from .errors import UNDataError, UNDataWarning
from .style import (
    ACCENT,
    BASELINE,
    CATEGORICAL,
    FAINT,
    GRID,
    INK,
    MUTED,
    SEQUENTIAL,
    SOFT,
    STATUS,
    WIDTH,
    Context,
    rc,
)
from .summary import fmt_number

if TYPE_CHECKING:
    from matplotlib.axes import Axes
    from matplotlib.figure import Figure

__all__ = ["chart"]

Kind = Literal[
    "auto",
    "bar",
    "line",
    "facets",
    "dumbbell",
    "slope",
    "progress",
    "gap",
    "heatmap",
    "profile",
    "scatter",
    "map",
]

MAX_LINES = len(CATEGORICAL)
MAX_BARS = 60
MAX_FACETS = 36
MAX_LABELLED_POINTS = 25
DARK_FILL = 0.55  # relative luminance below which text on a fill turns white
OLDEST_SHADE = 15  # years: values this old or older take the lightest shade

SHORT_STATUS = {
    "On track or target met": "On track",
    "Moderate progress, but acceleration needed": "Moderate",
    "Marginal progress, and significant acceleration needed": "Marginal",
    "Stagnation": "Stagnation",
    "Regression": "Regression",
    "Insufficient data": "No data",
}


# ── The frame every chart shares: header, content, caption ───────────────────


def _mpl() -> Any:
    try:
        import matplotlib as mpl  # noqa: PLC0415 — an optional dependency
    except ImportError as exc:  # pragma: no cover - exercised without matplotlib
        raise ImportError(
            'un.chart() needs matplotlib. Install it with: pip install "undata[charts]"'
        ) from exc
    return mpl


def _frame(
    content_height: float,
    *,
    context: Context,
    title: str,
    subtitle: str,
    caption: str,
    width: float | None = None,
) -> tuple[Figure, Any]:
    """A figure with a header and a caption; returns it and the content area's spec."""
    _mpl()
    from matplotlib.figure import Figure  # noqa: PLC0415
    from matplotlib.transforms import blended_transform_factory  # noqa: PLC0415

    size = float(rc(context)["font.size"])
    width = width or WIDTH[context]
    heading = _wrap(title, width, size * 1.4)
    sub = _wrap(subtitle, width, size) if subtitle else ""
    wrapped = _wrap(caption, width, size * 0.78)
    header = (size * 1.4 * 1.3 * _lines(heading) + size * 1.35 * _lines(sub) + size * 0.8) / 72
    footer = (size * 0.78 * 1.45 * _lines(wrapped) + size * 0.9) / 72
    fig = Figure(figsize=(width, header + content_height + footer), layout="constrained")
    grid = fig.add_gridspec(3, 1, height_ratios=[header, content_height, footer])
    top = fig.add_subplot(grid[0])
    top.axis("off")
    left = (
        0.1 / width
    )  # text starts at the figure's edge, not the chart's, so it can use the full width
    head = blended_transform_factory(fig.transFigure, top.transAxes)
    texts = [
        top.text(
            left,
            1,
            heading,
            fontsize=size * 1.4,
            fontweight="bold",
            color=INK,
            va="top",
            transform=head,
        )
    ]
    if sub:
        texts.append(
            top.text(
                left,
                0.1,
                sub,
                fontsize=size,
                color=SOFT,
                va="bottom",
                linespacing=1.3,
                transform=head,
            )
        )
    bottom = fig.add_subplot(grid[2])
    bottom.axis("off")
    foot = blended_transform_factory(fig.transFigure, bottom.transAxes)
    texts.append(
        bottom.text(
            left,
            0.9,
            wrapped,
            fontsize=size * 0.78,
            color=FAINT,
            va="top",
            linespacing=1.4,
            transform=foot,
        )
    )
    for text in texts:
        text.set_in_layout(False)  # wrapped to fit already; never let text squeeze the chart
    return fig, grid[1]


def _wrap(text: str, width: float, size: float) -> str:
    """Wrap ``text`` to a figure ``width`` in inches, at font ``size`` in points."""
    chars = max(int((width - 0.3) * 72 / (size * 0.55)), 20)
    return "\n".join(textwrap.fill(line, chars) for line in text.splitlines() if line)


def _lines(text: str) -> int:
    return text.count("\n") + 1 if text else 0


def _caption(table: pd.DataFrame, long: pd.DataFrame, note: str | None) -> str:
    sources = sorted({str(s) for s in long.get("source", pd.Series(dtype=str)).dropna()})
    retrieved = table.attrs.get("retrieved") or date.today().isoformat()
    first = (
        f"Source: {'; '.join(sources) or 'see table'}, via the UN System Data Commons "
        f"(data.un.org), retrieved {retrieved}."
    )
    method = table.attrs.get("method")
    if method:
        first += f" Assessment: {method['name']}."
    lines = [first]
    missing = sorted({m["country"] for m in table.attrs.get("missing") or []})
    stale = sorted({s["country"] for s in table.attrs.get("stale") or []})
    gaps = []
    if missing:
        gaps.append(f"No data: {_names(missing)}.")
    if stale:
        gaps.append(f"Left out as too old: {_names(stale)}.")
    if gaps:
        lines.append(" ".join(gaps))
    if note:
        lines.append(note)
    return "\n".join(lines)


def _names(items: Sequence[str], limit: int = 10) -> str:
    more = len(items) - limit
    return ", ".join(items[:limit]) + (f" and {more} more" if more > 0 else "")


def _style_axis(ax: Axes, *, grid: Literal["x", "y", "both", "none"] = "x") -> None:
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(BASELINE)
    ax.tick_params(colors=SOFT, length=0)
    ax.grid(False)
    if grid in ("x", "both"):
        ax.grid(axis="x", color=GRID, linewidth=0.8)
    if grid in ("y", "both"):
        ax.grid(axis="y", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)


def _unit(frame: pd.DataFrame) -> str:
    units = frame["unit"].dropna() if "unit" in frame else pd.Series(dtype=str)
    return str(units.iloc[0]) if len(units) else ""


def _one_indicator(long: pd.DataFrame) -> str:
    names = [str(n) for n in dict.fromkeys(long["indicator_name"])]
    if len(names) != 1:
        raise ValueError(
            f"un.chart() draws one indicator at a time, and this table has {len(names)}. "
            "Two indicators on one axis invent a relationship the data does not show. "
            'Chart them separately, for example table[table["indicator_name"] == name].'
        )
    return names[0]


def _short(name: str) -> str:
    """An indicator name without its bracketed breakdown, for titles."""
    return name.split(" [", maxsplit=1)[0]


def _ink_on(colour: str) -> str:
    """White or ink text, whichever reads on a fill."""
    r, g, b = (int(colour[i : i + 2], 16) / 255 for i in (1, 3, 5))
    return "white" if 0.2126 * r + 0.7152 * g + 0.0722 * b < DARK_FILL else INK


def _hex(rgba: Sequence[float]) -> str:
    return "#" + "".join(f"{round(c * 255):02X}" for c in rgba[:3])


def _box(x: float, y: float, colour: str, edge: str = "none", inset: float = 0.05) -> Any:
    from matplotlib.patches import Rectangle  # noqa: PLC0415

    side = 1 - 2 * inset
    return Rectangle(
        (x + inset, y + inset), side, side, facecolor=colour, edgecolor=edge, linewidth=1.2
    )


def _latest_per_country(long: pd.DataFrame) -> pd.DataFrame:
    rows = long.dropna(subset=["value"])
    if rows.empty or rows.groupby("country")["year"].nunique().max() <= 1:
        return rows
    return rows.sort_values("year").groupby("country", as_index=False).last()


def _legend(ax: Axes, rows: int) -> None:
    ax.legend(
        loc="upper left",
        bbox_to_anchor=(0, 1.04 + 0.5 / max(rows, 1)),
        ncols=3,
        frameon=False,
        fontsize="small",
    )


# ── Chart kinds ──────────────────────────────────────────────────────────────


def _bar(
    table: pd.DataFrame,
    long: pd.DataFrame,
    *,
    context: Context,
    title: str,
    note: str | None,
    highlight: set[str],
    benchmarks: dict[str, float],
) -> Figure:
    rows = _latest_per_country(long)
    if len(rows) > MAX_BARS:
        raise ValueError(f"{len(rows)} bars are too many to read. Pass top=20, or kind='map'.")
    rows = rows.sort_values("value")
    years = sorted({int(y) for y in rows["year"].dropna()})
    subtitle = _unit(long) + (
        f", {years[0]}" if len(years) == 1 else ", latest year for each country"
    )
    fig, spec = _frame(
        0.26 * len(rows) + 0.5,
        context=context,
        title=title,
        subtitle=subtitle,
        caption=_caption(table, long, note),
    )
    ax = fig.add_subplot(spec)
    colours = [ACCENT if not highlight or c in highlight else MUTED for c in rows["country"]]
    ax.barh(rows["country"], rows["value"], color=colours, height=0.62)
    top = float(rows["value"].max())
    for y, (value, year) in enumerate(zip(rows["value"], rows["year"], strict=True)):
        label = fmt_number(float(value)) + (f"  ({int(year)})" if len(years) > 1 else "")
        ax.text(value + top * 0.01, y, label, va="center", fontsize="small", color=INK)
    for name, value in benchmarks.items():
        ax.axvline(value, color=INK, linewidth=1, linestyle=(0, (4, 3)))
        ax.text(value, len(rows) - 0.3, f" {name} {fmt_number(value)}", fontsize="small", color=INK)
    _style_axis(ax, grid="x")
    ax.tick_params(axis="y", labelcolor=INK)
    ax.set_xlim(0, max([top, *benchmarks.values()]) * 1.16)
    ax.set_ylim(-0.6, len(rows) - 0.1 + (0.6 if benchmarks else 0))
    return fig


def _line(
    table: pd.DataFrame,
    long: pd.DataFrame,
    *,
    context: Context,
    title: str,
    note: str | None,
    highlight: set[str],
) -> Figure:
    from matplotlib.ticker import MaxNLocator  # noqa: PLC0415

    countries = sorted(set(long["country"]))
    fig, spec = _frame(
        3.4 if context == "report" else 4.6,
        context=context,
        title=title,
        subtitle=_unit(long),
        caption=_caption(table, long, note),
    )
    ax = fig.add_subplot(spec)
    for i, country in enumerate(countries):
        rows = long[long["country"] == country].dropna(subset=["value"]).sort_values("year")
        colour = CATEGORICAL[i] if not highlight or country in highlight else MUTED
        ax.plot(rows["year"], rows["value"], color=colour, linewidth=2, label=country)
        last = rows.iloc[-1]
        ax.annotate(
            f" {country} {fmt_number(float(last['value']))}",
            (last["year"], last["value"]),
            fontsize="small",
            color=INK,
            va="center",
        )
    _style_axis(ax, grid="y")
    ax.xaxis.set_major_locator(MaxNLocator(integer=True))
    ax.set_ylim(bottom=0)
    first, last = float(long["year"].min()), float(long["year"].max())
    span = max(last - first, 1.0)
    ax.set_xlim(first - span * 0.02, last + span * 0.22)  # room on the right for the end labels
    _legend(ax, 8)
    return fig


def _facets(
    table: pd.DataFrame,
    long: pd.DataFrame,
    *,
    context: Context,
    title: str,
    note: str | None,
    highlight: set[str],
) -> Figure:
    countries = sorted(set(long["country"]))
    if len(countries) > MAX_FACETS:
        raise ValueError(
            f"{len(countries)} panels are too many. Chart up to {MAX_FACETS} countries."
        )
    cols = 4 if context == "report" else 6
    rows = -(-len(countries) // cols)
    fig, spec = _frame(
        1.25 * rows + 0.2,
        context=context,
        title=title,
        subtitle=f"{_unit(long)}. Each panel is one country, with the others in grey behind it.",
        caption=_caption(table, long, note),
    )
    grid = spec.subgridspec(rows, cols, hspace=0.15, wspace=0.08)
    ceiling = float(long["value"].max()) * 1.08
    span = (int(long["year"].min()), int(long["year"].max()))
    for i, country in enumerate(countries):
        ax = fig.add_subplot(grid[i // cols, i % cols])
        for other in countries:
            others = long[long["country"] == other].sort_values("year")
            ax.plot(others["year"], others["value"], color=GRID, linewidth=1)
        mine = long[long["country"] == country].sort_values("year")
        colour = ACCENT if not highlight or country in highlight else SOFT
        ax.plot(mine["year"], mine["value"], color=colour, linewidth=2)
        ax.set_title(country, fontsize="small", color=INK, loc="left", pad=2)
        ax.set_ylim(0, ceiling)
        ax.set_xlim(*span)
        _style_axis(ax, grid="none")
        ax.set_xticks(list(span))
        if i % cols:
            ax.set_yticklabels([])
        if i // cols < rows - 1:
            ax.set_xticklabels([])
        ax.tick_params(labelsize="x-small")
    return fig


def _dumbbell(
    table: pd.DataFrame,
    rows: pd.DataFrame,
    *,
    start: tuple[str, str],
    end: tuple[str, str],
    context: Context,
    title: str,
    subtitle: str,
    note: str | None,
    highlight: set[str],
) -> Figure:
    """One row per place, a hollow dot at ``start`` and a filled one at ``end``."""
    long = long_of(table)
    rows = rows.dropna(subset=[start[0], end[0]]).sort_values(end[0]).reset_index(drop=True)
    fig, spec = _frame(
        0.3 * len(rows) + 0.6,
        context=context,
        title=title,
        subtitle=subtitle,
        caption=_caption(table, long, note),
    )
    ax = fig.add_subplot(spec)
    for y, (_, row) in enumerate(rows.iterrows()):
        a, b = float(row[start[0]]), float(row[end[0]])
        focus = not highlight or row["country"] in highlight
        ax.plot([a, b], [y, y], color=GRID if focus else "#F2F2F4", linewidth=2.2, zorder=1)
        ax.scatter(a, y, s=46, facecolor="white", edgecolor=MUTED, linewidth=1.6, zorder=3)
        ax.scatter(
            b, y, s=46, color=ACCENT if focus else MUTED, edgecolor="white", linewidth=1.2, zorder=4
        )
        ax.annotate(
            fmt_number(b),
            (b, y),
            xytext=(7 if b >= a else -7, 0),
            textcoords="offset points",
            ha="left" if b >= a else "right",
            va="center",
            fontsize="small",
            color=INK,
        )
    ax.set_yticks(range(len(rows)), rows["country"])
    _style_axis(ax, grid="x")
    ax.tick_params(axis="y", labelcolor=INK)
    ax.scatter([], [], s=46, facecolor="white", edgecolor=MUTED, label=start[1])
    ax.scatter([], [], s=46, color=ACCENT, label=end[1])
    _legend(ax, len(rows))
    low = float(rows[[start[0], end[0]]].min().min())
    high = float(rows[[start[0], end[0]]].max().max())
    pad = (high - low) * 0.14 or abs(high) * 0.1 or 1.0
    ax.set_xlim(low - pad, high + pad)
    return fig


def _slope(
    table: pd.DataFrame,
    *,
    context: Context,
    title: str,
    note: str | None,
    highlight: set[str],
) -> Figure:
    long = long_of(table)
    start, end = int(table["start_year"].min()), int(table["end_year"].max())
    fig, spec = _frame(
        3.6 if context == "report" else 4.8,
        context=context,
        title=title,
        subtitle=f"{_unit(table)}, {start} and {end}",
        caption=_caption(table, long, note),
        width=WIDTH[context] * 0.75,
    )
    ax = fig.add_subplot(spec)
    for _, row in table.iterrows():
        focus = not highlight or row["country"] in highlight
        a, b = float(row["start_value"]), float(row["end_value"])
        ax.plot(
            [0, 1],
            [a, b],
            color=ACCENT if focus else MUTED,
            linewidth=2 if focus else 1.2,
            marker="o",
            markersize=4,
        )
        text_colour = INK if focus else SOFT
        ax.text(
            -0.04,
            a,
            f"{row['country']} {fmt_number(a)}",
            ha="right",
            va="center",
            fontsize="small",
            color=text_colour,
        )
        ax.text(
            1.04,
            b,
            fmt_number(b),
            va="center",
            fontsize="small",
            color=text_colour,
        )
    ax.set_xticks([0, 1], [str(start), str(end)])
    ax.set_yticks([])
    _style_axis(ax, grid="none")
    ax.spines["bottom"].set_visible(False)
    ax.set_xlim(-0.9, 1.4)
    return fig


def _progress(
    table: pd.DataFrame,
    *,
    context: Context,
    title: str | None,
    note: str | None,
    highlight: set[str],
) -> Figure:
    long = long_of(table)
    assessment = table.attrs.get("assessment", {})
    target = assessment.get("target")
    rows = table.iloc[::-1].reset_index(drop=True)
    counts = ", ".join(
        f"{n} {SHORT_STATUS[s].lower()}" for s, n in table.attrs.get("summary", {}).items() if n
    )
    named = rows["indicator_name"].dropna()
    name = _short(str(named.iloc[0])) if len(named) else "the indicator"
    projection = (
        f"; hollow dot: projected {assessment.get('target_year', 2030)} at the current pace"
        if target is not None
        else ""
    )
    fig, spec = _frame(
        0.3 * len(rows) + 0.7,
        context=context,
        title=title or f"Progress on {name}",
        subtitle=f"{_unit(long)}. Grey dot: baseline; coloured dot: latest{projection}. {counts}.",
        caption=_caption(table, long, note),
    )
    ax = fig.add_subplot(spec)
    plotted = pd.concat([rows["baseline_value"], rows["latest_value"], rows["projected"]]).dropna()
    right = max(float(plotted.max()) if len(plotted) else 1.0, float(target or 0))
    for y, (_, row) in enumerate(rows.iterrows()):
        status = str(row["status"])
        colour = STATUS[status]
        faded = 0.35 if highlight and row["country"] not in highlight else 1.0
        if pd.notna(row["baseline_value"]) and pd.notna(row["latest_value"]):
            ax.plot(
                [row["baseline_value"], row["latest_value"]],
                [y, y],
                color=GRID,
                linewidth=2.2,
                zorder=1,
            )
            ax.scatter(row["baseline_value"], y, s=22, color=MUTED, zorder=2)
            if pd.notna(row["projected"]):
                ax.plot(
                    [row["latest_value"], row["projected"]],
                    [y, y],
                    color=colour,
                    linewidth=1,
                    linestyle=(0, (2, 2)),
                    zorder=1,
                )
                ax.scatter(
                    row["projected"],
                    y,
                    s=40,
                    facecolor="white",
                    edgecolor=colour,
                    linewidth=1.4,
                    zorder=3,
                )
            ax.scatter(
                row["latest_value"],
                y,
                s=58,
                color=colour,
                edgecolor="white",
                linewidth=1.2,
                zorder=4,
                alpha=faded,
            )
        side = ax.get_yaxis_transform()  # x in axes fractions, y in rows
        ax.scatter(1.02, y, s=30, marker="s", color=colour, transform=side, clip_on=False)
        ax.text(
            1.04, y, SHORT_STATUS[status], va="center", fontsize="small", color=INK, transform=side
        )
    if target is not None:
        ax.axvline(float(target), color=INK, linewidth=1, linestyle=(0, (4, 3)))
        ax.text(
            float(target),
            len(rows) - 0.25,
            f" target {fmt_number(float(target))}",
            fontsize="small",
            color=INK,
        )
    ax.set_yticks(range(len(rows)), rows["country"])
    _style_axis(ax, grid="x")
    ax.tick_params(axis="y", labelcolor=INK)
    ax.set_xlim(0, right * 1.04)
    ax.set_ylim(-0.7, len(rows) + 0.2)
    return fig


def _gap(
    table: pd.DataFrame,
    *,
    context: Context,
    title: str | None,
    note: str | None,
    highlight: set[str],
) -> Figure:
    long = long_of(table)
    first, second = table.attrs["gap"]["groups"]
    a_name, b_name = first.split(" (")[0], second.split(" (")[0]
    rows = table.sort_values("ratio").reset_index(drop=True)
    named = long["indicator_name"].dropna() if "indicator_name" in long else pd.Series(dtype=str)
    name = _short(str(named.iloc[0])) if len(named) else "Gap"
    fig, spec = _frame(
        0.3 * len(rows) + 0.6,
        context=context,
        title=title or f"{name}: {a_name.lower()} and {b_name.lower()}",
        subtitle=f"{_unit(table)}, latest year with both. Right: {a_name.lower()} as a ratio of {b_name.lower()}.",
        caption=_caption(table, long, note),
    )
    ax = fig.add_subplot(spec)
    a_colour, b_colour = CATEGORICAL[1], CATEGORICAL[0]
    right = float(rows[[first, second]].max().max())
    for y, (_, row) in enumerate(rows.iterrows()):
        faded = 0.35 if highlight and row["country"] not in highlight else 1.0
        ax.plot([row[first], row[second]], [y, y], color=GRID, linewidth=2.2, zorder=1)
        for value, colour in ((row[first], a_colour), (row[second], b_colour)):
            ax.scatter(
                value,
                y,
                s=50,
                color=colour,
                edgecolor="white",
                linewidth=1.2,
                zorder=3,
                alpha=faded,
            )
        if pd.notna(row.get("ratio")):
            ax.text(
                right * 1.05,
                y,
                f"{row['ratio']:.2f}  ({int(row['year'])})",
                va="center",
                fontsize="small",
                color=INK,
            )
    ax.set_yticks(range(len(rows)), rows["country"])
    _style_axis(ax, grid="x")
    ax.tick_params(axis="y", labelcolor=INK)
    ax.scatter([], [], s=50, color=a_colour, label=a_name)
    ax.scatter([], [], s=50, color=b_colour, label=b_name)
    _legend(ax, len(rows))
    ax.set_xlim(0, right * 1.3)
    return fig


def _heatmap(
    table: pd.DataFrame, *, context: Context, title: str | None, note: str | None
) -> Figure:
    from matplotlib.colors import LinearSegmentedColormap  # noqa: PLC0415

    long = long_of(table)
    this_year = date.today().year
    labels = [
        "\n".join(textwrap.wrap(_short(str(c)), 22, max_lines=3, placeholder=" …"))
        for c in table.columns
    ]
    fig, spec = _frame(
        0.26 * len(table) + 0.9,
        context=context,
        title=title or "Which countries report what, and how recently",
        subtitle="Each cell is the year of the latest value; darker is more recent. A dash means no data.",
        caption=_caption(table, long, note),
        width=min(WIDTH[context], 2.4 + 1.3 * len(table.columns)),
    )
    ax = fig.add_subplot(spec)
    ramp = LinearSegmentedColormap.from_list("recent", list(SEQUENTIAL))
    for y, country in enumerate(table.index):
        for x, column in enumerate(table.columns):
            year = table.loc[country, column]
            if pd.isna(year):
                ax.add_patch(_box(x, y, "#F4F4F6", inset=0.04))
                ax.text(
                    x + 0.5,
                    y + 0.5,
                    "\u2013",
                    ha="center",
                    va="center",
                    fontsize="x-small",
                    color=FAINT,
                )
                continue
            age = min(max(this_year - int(year), 0), OLDEST_SHADE)
            colour = _hex(ramp(1 - age / OLDEST_SHADE))
            ax.add_patch(_box(x, y, colour, inset=0.04))
            ax.text(
                x + 0.5,
                y + 0.5,
                str(int(year)),
                ha="center",
                va="center",
                fontsize="x-small",
                color=_ink_on(colour),
            )
    ax.set_xlim(0, len(table.columns))
    ax.set_ylim(len(table), 0)
    ax.set_yticks([i + 0.5 for i in range(len(table))], list(table.index))
    ax.set_xticks([i + 0.5 for i in range(len(table.columns))], labels)
    ax.xaxis.tick_top()
    ax.tick_params(length=0, labelsize="small", colors=INK)
    for side in ax.spines.values():
        side.set_visible(False)
    return fig


def _profile(
    table: pd.DataFrame, *, context: Context, title: str | None, note: str | None
) -> Figure:
    info = table.attrs.get("profile", {})
    country, region = info.get("country", ""), info.get("region", "region")
    rows = table.reset_index(drop=True)
    fig, spec = _frame(
        0.62 * len(rows) + 0.4,
        context=context,
        title=title or f"{country}: where it stands",
        subtitle=f"Latest value for {country}, beside the published figures for {region} and the world. Each row has its own scale.",
        caption=_caption(table, long_of(table), note),
    )
    grid = spec.subgridspec(len(rows) + 1, 1, height_ratios=[0.35] + [1.0] * len(rows))
    marks = (
        ("world_value", "World", "D", INK),
        ("region_value", region, "s", MUTED),
        ("value", country, "o", ACCENT),
    )
    for i, (_, row) in enumerate(rows.iterrows()):
        ax = fig.add_subplot(grid[i + 1])
        values = [float(row[c]) for c, *_ in marks if pd.notna(row[c])]
        ceiling = max(values) * 1.15 if values else 1.0
        ax.plot([0, ceiling], [0, 0], color=GRID, linewidth=2, zorder=1)
        for column, who, marker, colour in marks:
            if pd.notna(row[column]):
                value = float(row[column])
                ax.scatter(
                    value,
                    0,
                    s=70 if who == country else 48,
                    marker=marker,
                    color=colour,
                    edgecolor="white",
                    zorder=3,
                    label=who,
                )
                below = (
                    who == region
                )  # the region's label goes under the line, so labels never collide
                ax.annotate(
                    fmt_number(value),
                    (value, 0),
                    xytext=(0, -8 if below else 7),
                    textcoords="offset points",
                    ha="center",
                    va="top" if below else "bottom",
                    fontsize="x-small",
                    color=SOFT if below else INK,
                )
        rank = (
            f"  ·  {ordinal(int(row['rank']), int(row['out_of']))} in {region}"
            if pd.notna(row["rank"])
            else ""
        )
        year = f" ({int(row['year'])})" if pd.notna(row["year"]) else ""
        ax.set_title(
            f"{_short(str(row['indicator_name']))}{year}{rank}",
            fontsize="small",
            loc="left",
            color=INK,
            pad=10,
        )
        ax.set_xlim(0, ceiling)
        ax.set_yticks([])
        ax.set_xticks([])  # every mark is labelled, and each row has its own scale
        ax.spines["bottom"].set_visible(False)
        _style_axis(ax, grid="none")
        ax.tick_params(labelsize="x-small")
        ax.set_ylim(-1, 1)
        if i == 0:
            key = fig.add_subplot(grid[0])
            key.axis("off")
            handles, labels = ax.get_legend_handles_labels()
            key.legend(handles, labels, loc="center left", ncols=3, frameon=False, borderaxespad=0)
    return fig


def _scatter(
    table: pd.DataFrame,
    *,
    context: Context,
    title: str | None,
    note: str | None,
    highlight: set[str],
) -> Figure:
    long = long_of(table)
    labels = [
        c for c in table.columns if c not in ("country", "iso3") and not str(c).endswith(" year")
    ]
    if len(labels) != 2:  # noqa: PLR2004
        raise ValueError("A scatter needs a un.compare() table of exactly two indicators.")
    x, y = labels
    both = table.dropna(subset=[x, y]).reset_index(drop=True)
    coverage = table.attrs.get("coverage", {})
    asked = len(coverage.get("all", [])) + sum(len(v) for v in coverage.get("only", {}).values())
    asked += len(coverage.get("none", []))
    fig, spec = _frame(
        3.8 if context == "report" else 5.0,
        context=context,
        title=title or f"{_short(x)} and {_short(y)}",
        subtitle=f"{len(both)} countries with both, of {asked or len(table)} asked for; each at its latest year.",
        caption=_caption(table, long, note),
        width=WIDTH[context] * 0.8,
    )
    ax = fig.add_subplot(spec)
    colours = [ACCENT if not highlight or c in highlight else MUTED for c in both["country"]]
    ax.scatter(both[x], both[y], s=46, color=colours, edgecolor="white", linewidth=1, zorder=3)
    named = set(highlight)
    if len(both) > MAX_LABELLED_POINTS:  # too many to label: name the extremes on each axis
        for column in (x, y):
            named |= set(both.nlargest(2, column)["country"]) | set(
                both.nsmallest(2, column)["country"]
            )
    spans = (
        float(both[x].max() - both[x].min()) or 1.0,
        float(both[y].max() - both[y].min()) or 1.0,
    )
    placed: list[tuple[float, float]] = []
    for _, row in both.iterrows():
        if len(both) > MAX_LABELLED_POINTS and row["country"] not in named:
            continue
        px, py = float(row[x]) / spans[0], float(row[y]) / spans[1]
        crowded = any(abs(px - qx) < 0.12 and abs(py - qy) < 0.05 for qx, qy in placed)  # noqa: PLR2004
        placed.append((px, py))
        ax.annotate(
            row["country"],
            (row[x], row[y]),
            xytext=(-4, -4) if crowded else (4, 3),  # a near neighbour is labelled: go below-left
            textcoords="offset points",
            ha="right" if crowded else "left",
            va="top" if crowded else "bottom",
            fontsize="x-small",
            color=INK,
        )
    ax.set_xlabel(textwrap.fill(x, 60))
    ax.set_ylabel(textwrap.fill(y, 45))
    _style_axis(ax, grid="both")
    ax.spines["left"].set_visible(True)
    ax.spines["left"].set_color(BASELINE)
    return fig


@cache
def _tiles() -> dict[str, tuple[int, int]]:
    text = resources.files("undata").joinpath("tiles.csv").read_text(encoding="utf-8")
    return {r["iso3"]: (int(r["row"]), int(r["col"])) for r in csv.DictReader(text.splitlines())}


def _map(
    table: pd.DataFrame,
    long: pd.DataFrame,
    *,
    context: Context,
    title: str,
    note: str | None,
    highlight: set[str],
) -> Figure:
    from matplotlib.cm import ScalarMappable  # noqa: PLC0415
    from matplotlib.colors import LinearSegmentedColormap, Normalize  # noqa: PLC0415

    from .places import m49  # noqa: PLC0415

    rows = _latest_per_country(long)
    tiles = _tiles()
    rows = rows[rows["iso3"].isin(tiles)]
    values = dict(zip(rows["iso3"].astype(str), rows["value"].astype(float), strict=True))
    if not values:
        raise ValueError("None of these places has a tile. A tile map needs countries.")
    asked_names = {m["country"] for m in table.attrs.get("missing") or []} | set(rows["country"])
    asked = ({c.iso3 for c in m49() if c.name in asked_names} | set(values)) & set(tiles)
    marked = {_iso(name) for name in highlight}
    # Crop to the countries asked for, so a regional table draws a regional map.
    cells = [tiles[i] for i in asked]
    r0, c0 = min(r for r, _ in cells), min(c for _, c in cells)
    rows_span = max(r for r, _ in cells) - r0 + 1
    cols_span = max(c for _, c in cells) - c0 + 1
    cell = min(WIDTH[context] / cols_span, 0.42 if context == "report" else 0.55)
    years = sorted({int(y) for y in rows["year"].dropna()})
    when = (
        f", {years[0]}" if len(years) == 1 else f", latest year for each ({years[0]}-{years[-1]})"
    )
    fig, spec = _frame(
        cell * rows_span + 0.55,
        context=context,
        title=title,
        subtitle=_unit(long) + when + ". One square per country; grey: no data.",
        caption=_caption(table, long, note),
        width=max(WIDTH[context] * 0.6, cell * cols_span + 0.4),
    )
    grid = spec.subgridspec(2, 1, height_ratios=[cell * rows_span, 0.35])
    ax = fig.add_subplot(grid[0])
    ramp = LinearSegmentedColormap.from_list("values", list(SEQUENTIAL))
    low, high = min(values.values()), max(values.values())
    norm = Normalize(vmin=low, vmax=high if high > low else low + 1)
    text_size = 5.6 if context == "report" else 7.5
    for iso in sorted(asked):
        row, col = tiles[iso]
        x, y = col - c0, row - r0
        if iso in values:
            colour = _hex(ramp(norm(values[iso])))
            ax.add_patch(_box(x, y, colour, INK if iso in marked else "white"))
            ax.text(
                x + 0.5,
                y + 0.52,
                iso,
                ha="center",
                va="center",
                fontsize=text_size,
                color=_ink_on(colour),
            )
        else:
            ax.add_patch(_box(x, y, "#F4F4F6", "#DADAE0"))
            ax.text(
                x + 0.5, y + 0.52, iso, ha="center", va="center", fontsize=text_size, color=FAINT
            )
    ax.set_xlim(-0.1, cols_span + 0.1)
    ax.set_ylim(rows_span + 0.1, -0.1)
    ax.set_aspect("equal")
    ax.axis("off")
    key = fig.add_subplot(grid[1])
    bar = fig.colorbar(ScalarMappable(norm=norm, cmap=ramp), cax=key, orientation="horizontal")
    bar.outline.set_visible(False)
    bar.ax.tick_params(labelsize="x-small", colors=SOFT, length=0)
    key.set_box_aspect(0.035)
    return fig


def _iso(name: str) -> str | None:
    from .places import resolve  # noqa: PLC0415

    try:
        return resolve(name).iso3
    except UNDataError:
        return None


# ── Choosing and drawing ─────────────────────────────────────────────────────


def _detect(table: pd.DataFrame) -> str:
    attrs = table.attrs
    columns = set(table.columns)
    if "method" in attrs and "status" in columns:
        return "progress"
    if "gap" in attrs:
        return "gap"
    if "profile" in attrs:
        return "profile"
    if "availability" in attrs:
        return "heatmap"
    if "coverage" in attrs and "indicator" not in columns:
        return "scatter"
    if "start_value" in columns or {"place", "baseline_value"} <= columns:
        return "dumbbell"
    long = long_of(table)
    if long.empty:
        raise ValueError("The table is empty, so there is nothing to chart.")
    several = long.groupby("country")["year"].nunique().max()
    if several and several > 1:
        return "line" if long["country"].nunique() <= MAX_LINES else "facets"
    return "bar"


def chart(
    table: pd.DataFrame,
    path: str | Path | None = None,
    *,
    kind: Kind = "auto",
    highlight: str | Sequence[str] | None = None,
    title: str | None = None,
    note: str | None = None,
    benchmarks: Sequence[str] | None = None,
    top: int | None = None,
    context: Context = "report",
    interactive: bool = False,
) -> Any:
    """Draw a production-quality chart of a table from undata, chosen from its shape.

    Args:
        table: A table from any undata function. The module help lists which chart
            each draws.
        path: Save the chart too: ``.png`` (300 dpi), ``.svg`` or ``.pdf`` (editable
            text), or ``.html`` for an interactive chart.
        kind: Override the choice: ``"bar"``, ``"line"``, ``"facets"``,
            ``"dumbbell"``, ``"slope"``, ``"progress"``, ``"gap"``, ``"heatmap"``,
            ``"profile"``, ``"scatter"`` or ``"map"``.
        highlight: Countries to draw in colour, with the rest in grey.
        title: The title. Defaults to the indicator's name.
        note: A line added under the source, such as a definition.
        benchmarks: For bars: regions or groups whose published figure is drawn as a
            reference line, such as ``["World", "Western Africa"]``.
        top: For bars: keep only the highest ``top`` values.
        context: ``"report"`` for documents, ``"slides"`` for presentations.
        interactive: Draw an interactive Plotly chart instead (``pip install plotly``).

    Returns:
        A matplotlib figure (it displays itself in a notebook), or a Plotly figure.

    Example:
        >>> import undata as un
        >>> table = un.latest("undata/sdg/EG_ACS_ELEC", "Western Africa")  # doctest: +SKIP
        >>> un.chart(table, "electricity.svg", benchmarks=["World"])  # doctest: +SKIP
    """
    focus = {highlight} if isinstance(highlight, str) else set(highlight or [])
    chosen = _detect(table) if kind == "auto" else kind
    if interactive:
        from ._interactive import draw  # noqa: PLC0415

        figure = draw(table, chosen, title=title, highlight=focus)
        if path is not None:
            figure.write_html(str(path), include_plotlyjs="cdn")
        return figure
    mpl = _mpl()
    with mpl.rc_context(rc(context)):
        fig = _draw(
            table,
            chosen,
            context=context,
            title=title,
            note=note,
            highlight=focus,
            benchmarks=benchmarks,
            top=top,
        )
    if path is not None:
        fig.savefig(Path(path), dpi=300, bbox_inches="tight", facecolor="white")
    return fig


def _draw(
    table: pd.DataFrame,
    kind: str,
    *,
    context: Context,
    title: str | None,
    note: str | None,
    highlight: set[str],
    benchmarks: Sequence[str] | None,
    top: int | None,
) -> Figure:
    special: dict[str, Callable[[], Figure]] = {
        "progress": lambda: _progress(
            table, context=context, title=title, note=note, highlight=highlight
        ),
        "gap": lambda: _gap(table, context=context, title=title, note=note, highlight=highlight),
        "heatmap": lambda: _heatmap(table, context=context, title=title, note=note),
        "profile": lambda: _profile(table, context=context, title=title, note=note),
        "scatter": lambda: _scatter(
            table, context=context, title=title, note=note, highlight=highlight
        ),
    }
    if kind in special:
        return special[kind]()
    if kind in ("dumbbell", "slope"):
        return _paired(table, kind, context=context, title=title, note=note, highlight=highlight)
    long = long_of(table)
    if long.empty:
        raise ValueError("The table is empty, so there is nothing to chart.")
    heading = title or _short(_one_indicator(long))
    if kind == "line":
        if long["country"].nunique() > MAX_LINES:
            raise ValueError(
                f"{long['country'].nunique()} countries are too many lines to read. Chart up "
                f"to {MAX_LINES}, or use kind='facets' for small multiples."
            )
        return _line(table, long, context=context, title=heading, note=note, highlight=highlight)
    if kind == "facets":
        return _facets(table, long, context=context, title=heading, note=note, highlight=highlight)
    if kind == "map":
        return _map(table, long, context=context, title=heading, note=note, highlight=highlight)
    rows = long
    if top is not None:
        latest_rows = _latest_per_country(long)
        keep = set(latest_rows.nlargest(top, "value")["country"])
        rows = long[long["country"].isin(keep)]
    reference = _benchmarks(long, benchmarks)
    return _bar(
        table,
        rows,
        context=context,
        title=heading,
        note=note,
        highlight=highlight,
        benchmarks=reference,
    )


def _benchmarks(long: pd.DataFrame, names: Sequence[str] | None) -> dict[str, float]:
    if not names:
        return {}
    from .data import totals  # noqa: PLC0415

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UNDataWarning)
        found = totals(str(long["indicator"].iloc[0]), list(names), latest=True)
    return dict(zip(found["country"].astype(str), found["value"].astype(float), strict=True))


def _paired(
    table: pd.DataFrame,
    kind: str,
    *,
    context: Context,
    title: str | None,
    note: str | None,
    highlight: set[str],
) -> Figure:
    if "place" in table.columns:  # benchmark()
        frame = table.rename(columns={"place": "country"})
        start = ("baseline_value", str(int(frame["baseline_year"].min())))
        end = ("latest_value", "latest")
    elif "start_value" in table.columns:  # change() or trend()
        frame = table
        start = ("start_value", str(int(frame["start_year"].min())))
        end = ("end_value", str(int(frame["end_year"].max())))
    else:
        raise ValueError(
            f'kind="{kind}" needs a table from un.change(), un.trend() or un.benchmark().'
        )
    names = [str(n) for n in dict.fromkeys(frame["indicator_name"])]
    if len(names) != 1:
        raise ValueError("un.chart() draws one indicator at a time; filter the table first.")
    heading = title or _short(names[0])
    if kind == "slope":
        if "start_value" not in frame.columns:
            raise ValueError('kind="slope" needs a table from un.change() or un.trend().')
        return _slope(frame, context=context, title=heading, note=note, highlight=highlight)
    return _dumbbell(
        table,
        frame,
        start=start,
        end=end,
        context=context,
        title=heading,
        subtitle=_unit(frame),
        note=note,
        highlight=highlight,
    )
