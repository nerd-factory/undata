"""Quick, honest charts for slides and reports.

:func:`chart` picks the chart from the table's shape: ranked bars for one value per
country, lines for several years, a dumbbell for :func:`undata.change`. Every chart
carries its source, the years, and the countries with no data, so it can be pasted
into a slide without losing what makes it trustworthy.

It needs matplotlib: ``pip install "undata[charts]"``.

Rules it keeps, whatever the data: one indicator per chart (never two scales on one
axis), at most six lines (more is a bar chart), and every line labelled at its end,
so colour is never the only way to tell them apart.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

import pandas as pd

from .summary import fmt_number

if TYPE_CHECKING:
    from matplotlib.figure import Figure

__all__ = ["chart"]

#: Okabe-Ito hues, reordered so neighbours differ most. Checked for colour-vision
#: deficiency; the closest pair needs the end labels every line gets.
LINE_COLOURS = ("#0072B2", "#D55E00", "#009E73", "#CC79A7", "#E69F00", "#56B4E9")
ACCENT = "#0072B2"
MUTED = "#A3A3A3"
INK = "#1F1F24"
FAINT = "#6B6B70"
GRID = "#E4E4E7"
MAX_LINES = len(LINE_COLOURS)
MAX_NAMED = 6  # countries named in the "No data" line before "and N more"

Kind = Literal["auto", "bar", "line", "dumbbell"]


def _figure(width: float, height: float) -> Figure:
    try:
        from matplotlib.figure import Figure  # noqa: PLC0415 — an optional dependency
    except ImportError as exc:  # pragma: no cover - exercised without matplotlib
        raise ImportError(
            'un.chart() needs matplotlib. Install it with: pip install "undata[charts]"'
        ) from exc
    return Figure(figsize=(width, height), dpi=100, layout="constrained")


def _style(ax: Any) -> None:
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(GRID)
    ax.tick_params(colors=FAINT, labelsize=9, length=0)
    ax.grid(axis="x", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)


def _caption(table: pd.DataFrame, long: pd.DataFrame) -> str:
    sources = sorted({str(s) for s in long.get("source", pd.Series(dtype=str)).dropna()})
    retrieved = table.attrs.get("retrieved") or date.today().isoformat()
    text = (
        f"Source: {'; '.join(sources) or 'see table'}, via the UN System Data Commons "
        f"(data.un.org). Retrieved {retrieved}."
    )
    missing = sorted({m["country"] for m in table.attrs.get("missing") or []})
    if missing:
        more = len(missing) - MAX_NAMED
        shown = ", ".join(missing[:MAX_NAMED]) + (f" and {more} more" if more > 0 else "")
        text += f"\nNo data: {shown}."
    return text


def _one_indicator(long: pd.DataFrame) -> str:
    names = [str(n) for n in dict.fromkeys(long["indicator_name"])]
    if len(names) != 1:
        raise ValueError(
            f"un.chart() draws one indicator at a time, and this table has {len(names)}. "
            "Two indicators on one axis invent a relationship the data does not show. "
            'Chart them separately, for example table[table["indicator_name"] == name].'
        )
    return names[0]


def _bar(long: pd.DataFrame, title: str, highlight: set[str]) -> Figure:
    rows = long.sort_values("value")
    fig = _figure(8, 1.2 + 0.32 * len(rows))
    ax = fig.add_subplot()
    # One series is one colour; with a highlight, the rest step back to grey.
    colours = [ACCENT if not highlight or c in highlight else MUTED for c in rows["country"]]
    ax.barh(rows["country"], rows["value"], color=colours, height=0.6)
    for y, (value, year) in enumerate(zip(rows["value"], rows["year"], strict=True)):
        ax.text(value, y, f"  {fmt_number(value)}  ({year})", va="center", fontsize=8, color=INK)
    _style(ax)
    ax.tick_params(axis="y", labelcolor=INK, labelsize=9)
    ax.set_xlim(0, rows["value"].max() * 1.18)
    ax.set_title(title, loc="left", fontsize=12, color=INK, fontweight="bold")
    return fig


def _line(long: pd.DataFrame, title: str, highlight: set[str]) -> Figure:
    from matplotlib.ticker import MaxNLocator  # noqa: PLC0415 — an optional dependency

    countries = list(dict.fromkeys(long["country"]))
    if len(countries) > MAX_LINES:
        raise ValueError(
            f"{len(countries)} countries are too many lines to read. Chart up to "
            f"{MAX_LINES}, or use un.latest() for a ranked bar chart of all of them."
        )
    fig = _figure(8, 4.5)
    ax = fig.add_subplot()
    for i, country in enumerate(countries):
        rows = long[long["country"] == country].sort_values("year")
        colour = LINE_COLOURS[i] if not highlight or country in highlight else MUTED
        ax.plot(rows["year"], rows["value"], color=colour, linewidth=2, solid_capstyle="round")
        last = rows.iloc[-1]
        ax.annotate(
            f" {country}  {fmt_number(last['value'])}",
            (last["year"], last["value"]),
            fontsize=8,
            color=INK,
            va="center",
        )
    _style(ax)
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    ax.grid(axis="x", visible=False)
    ax.xaxis.set_major_locator(MaxNLocator(integer=True))
    ax.set_ylim(bottom=0)
    ax.set_title(title, loc="left", fontsize=12, color=INK, fontweight="bold")
    return fig


def _dumbbell(table: pd.DataFrame, title: str, highlight: set[str]) -> Figure:
    rows = table.sort_values("end_value")
    start, end = int(rows["start_year"].iloc[0]), int(rows["end_year"].iloc[0])
    fig = _figure(8, 1.5 + 0.34 * len(rows))
    ax = fig.add_subplot()
    for y, row in enumerate(rows.itertuples()):
        focus = not highlight or row.country in highlight
        link = GRID if focus else "#F0F0F2"
        ax.plot([row.start_value, row.end_value], [y, y], color=link, linewidth=2)
        ax.scatter(
            row.start_value, y, s=40, facecolor="white", edgecolor=MUTED, linewidth=1.6, zorder=3
        )
        ax.scatter(row.end_value, y, s=40, color=ACCENT if focus else MUTED, zorder=3)
    ax.set_yticks(range(len(rows)), rows["country"])
    _style(ax)
    ax.tick_params(axis="y", labelcolor=INK, labelsize=9)
    ax.scatter([], [], s=40, facecolor="white", edgecolor=MUTED, label=str(start))
    ax.scatter([], [], s=40, color=ACCENT, label=str(end))
    ax.legend(loc="lower right", frameon=False, fontsize=9)
    ax.set_title(title, loc="left", fontsize=12, color=INK, fontweight="bold")
    return fig


def chart(
    table: pd.DataFrame,
    path: str | Path | None = None,
    *,
    kind: Kind = "auto",
    highlight: str | list[str] | None = None,
    title: str | None = None,
) -> Figure:
    """Draw a chart of a table, with its source underneath, ready for a slide.

    Args:
        table: A table from :func:`undata.get`, :func:`undata.latest`,
            :func:`undata.totals`, :func:`undata.change` or :func:`undata.wide`,
            holding one indicator.
        path: Save the chart here too, as ``.png``, ``.svg`` or ``.pdf``.
        kind: ``"bar"``, ``"line"`` or ``"dumbbell"``. Left as ``"auto"``, it follows
            the table: several years per country draws lines, a change table a
            dumbbell, anything else ranked bars.
        highlight: One or more countries to draw in colour, with the rest in grey.
        title: The chart's title. Defaults to the indicator's name.

    Returns:
        A matplotlib figure. In a notebook it displays itself.

    Example:
        >>> import undata as un
        >>> sahel = ["Chad", "Niger", "Mali", "Burkina Faso", "Mauritania", "Sudan"]
        >>> un.chart(un.latest("undata/sdg/EG_ACS_ELEC", sahel), highlight="Chad")  # doctest: +SKIP
    """
    focus = {highlight} if isinstance(highlight, str) else set(highlight or [])
    if "change_pct" in table.columns:
        long, chosen = table, "dumbbell"
    else:
        long = table.attrs.get("long", table)
        several = long.groupby("country")["year"].nunique().max() if not long.empty else 0
        chosen = "line" if several and several > 1 else "bar"
    if long.empty:
        raise ValueError("The table is empty, so there is nothing to chart.")
    if kind != "auto":
        chosen = kind
    name = _one_indicator(long)
    heading = title or name
    if chosen == "dumbbell":
        if "change_pct" not in table.columns:
            raise ValueError('kind="dumbbell" needs a table from un.change().')
        fig = _dumbbell(table, heading, focus)
    elif chosen == "line":
        fig = _line(long, heading, focus)
    else:
        if long.groupby("country")["year"].nunique().max() > 1:
            long = long.sort_values("year").groupby("country", as_index=False).last()
        fig = _bar(long, heading, focus)
    unit = long["unit"].dropna().iloc[0] if "unit" in long and long["unit"].notna().any() else ""
    fig.supxlabel(unit, fontsize=9, color=FAINT, x=0.02, ha="left")
    caption = _caption(table, long)
    fig.text(0.0, -0.02, caption, fontsize=7.5, color=FAINT, ha="left", va="top", wrap=True)
    if path is not None:
        fig.savefig(Path(path), dpi=200, bbox_inches="tight", facecolor="white")
    return fig
