"""Inline SVG charts for the use-cases page, in the Nerd Lab palette.

Two forms cover every chart on the page:

* ``bars`` - one measure across countries, ranked. Emphasis, not categories: the
  country the story is about is in the accent, the rest in the de-emphasis grey.
* ``dumbbell`` - before and after per country. A hollow ring for the earlier year,
  a filled dot for the later one, so the two read apart without colour too.

Marks follow the dataviz rules: bars at most 24px thick with a 4px rounded end at the
value and a square end at the baseline, 2px lines, dots of radius 5 with a 2px ring
in the surface colour, solid hairline gridlines, dashed lines only for targets. Every
row has a full-height hover target with a native tooltip, and every chart sits next
to the table that holds the same numbers.
"""

from __future__ import annotations

import html
import math
import warnings
from collections.abc import Callable, Sequence
from dataclasses import dataclass

import undata as un

Format = Callable[[float], str]

WIDTH = 640
ROW = 28  # row pitch; also the hover target height, above the 24px minimum
BAR = 16  # bar thickness
TOP = 30  # room for target labels and the legend
AXIS = 26  # room for tick labels under the plot


@dataclass(frozen=True)
class Ref:
    """A target or benchmark drawn as a dashed vertical line."""

    value: float
    label: str


def _esc(text: str) -> str:
    return html.escape(text, quote=True)


def _nice_max(value: float, steps: int = 4) -> float:
    """Round a maximum up to a clean axis end that divides into clean ticks."""
    if value <= 0:
        return 1.0
    power = 10 ** math.floor(math.log10(value))
    candidates = (1, 2, 4, 5, 10) if steps == 2 else (1, 2, 2.5, 5, 10)
    for step in candidates:
        if value <= step * power:
            return step * power
    return 10 * power


def _ticks(top: float, steps: int = 4) -> list[float]:
    return [top * i / steps for i in range(steps + 1)]


def _bar_path(x0: float, y: float, width: float, height: float) -> str:
    """A bar rounded 4px at its data end and square at the baseline."""
    if width <= 4:
        return f'<rect x="{x0:.1f}" y="{y:.1f}" width="{max(width, 1):.1f}" height="{height}"/>'
    r = 4
    return (
        f'<path d="M{x0:.1f},{y:.1f} h{width - r:.1f} a{r},{r} 0 0 1 {r},{r} '
        f'v{height - 2 * r} a{r},{r} 0 0 1 -{r},{r} h-{width - r:.1f} z"/>'
    )


def _label_width(labels: Sequence[str], minimum: float) -> float:
    """Room for the longest label at 13px, bold included, so no name is clipped."""
    return max(minimum, 14 + 7.8 * max((len(label) for label in labels), default=0))


def _frame(title: str, height: float, body: list[str], label_w: float) -> str:
    return (
        f'<svg class="chart" viewBox="0 0 {WIDTH} {height:.0f}" role="img" '
        f'aria-label="{_esc(title)}" preserveAspectRatio="xMinYMin meet" '
        f'style="--label:{label_w}px"><title>{_esc(title)}</title>{"".join(body)}</svg>'
    )


def _axis(
    x: Callable[[float], float],
    top: float,
    plot_top: float,
    plot_bottom: float,
    fmt: Format,
    *,
    steps: int = 4,
) -> list[str]:
    parts = []
    for tick in _ticks(top, steps):
        px = x(tick)
        parts.append(
            f'<line class="grid" x1="{px:.1f}" x2="{px:.1f}" y1="{plot_top}" y2="{plot_bottom}"/>'
        )
        parts.append(
            f'<text class="tick" x="{px:.1f}" y="{plot_bottom + 16}" text-anchor="middle">{_esc(fmt(tick))}</text>'
        )
    return parts


def _refs(
    refs: Sequence[Ref], x: Callable[[float], float], plot_top: float, plot_bottom: float
) -> list[str]:
    parts = []
    for ref in refs:
        px = x(ref.value)
        parts.append(
            f'<line class="ref" x1="{px:.1f}" x2="{px:.1f}" y1="{plot_top - 8}" y2="{plot_bottom}"/>'
        )
        parts.append(
            f'<text class="ref-label" x="{px:.1f}" y="{plot_top - 12}" text-anchor="middle">{_esc(ref.label)}</text>'
        )
    return parts


def bars(
    rows: Sequence[tuple[str, float, str]],
    *,
    title: str,
    fmt: Format,
    highlight: Sequence[str] = (),
    refs: Sequence[Ref] = (),
    label_w: float = 190,
    width: float = WIDTH,
) -> str:
    """Horizontal bars, largest first. Each row is (label, value, tooltip detail)."""
    rows = sorted(rows, key=lambda r: r[1], reverse=True)
    label_w = _label_width([r[0] for r in rows], label_w)
    steps = 4 if width >= 480 else 2  # narrow panels get three ticks
    top = _nice_max(max([r[1] for r in rows] + [ref.value for ref in refs]), steps)
    x0, x1 = label_w, width - 56
    plot_top = TOP
    plot_bottom = plot_top + ROW * len(rows)

    def x(v: float) -> float:
        return x0 + (x1 - x0) * v / top

    body = _axis(x, top, plot_top, plot_bottom, fmt, steps=steps)
    body += _refs(refs, x, plot_top, plot_bottom)  # under the rows, so labels sit on top
    for i, (label, value, detail) in enumerate(rows):
        y = plot_top + i * ROW
        hi = label in highlight
        cls = "row hi" if hi else "row"
        body.append(
            f'<g class="{cls}"><title>{_esc(label)}: {_esc(fmt(value))} {_esc(detail)}</title>'
            f'<rect class="hit" x="0" y="{y}" width="{width}" height="{ROW}"/>'
            f'<text class="label" x="{x0 - 10}" y="{y + ROW / 2 + 4}" text-anchor="end">{_esc(label)}</text>'
            f'<g class="bar">{_bar_path(x0, y + (ROW - BAR) / 2, x(value) - x0, BAR)}</g>'
            f'<text class="value" x="{x(value) + 6:.1f}" y="{y + ROW / 2 + 4}">{_esc(fmt(value))}</text></g>'
        )
    body.append(f'<line class="baseline" x1="{x0}" x2="{x0}" y1="{plot_top}" y2="{plot_bottom}"/>')
    svg = _frame(title, plot_bottom + AXIS, body, label_w)
    return svg.replace(f'viewBox="0 0 {WIDTH} ', f'viewBox="0 0 {width:.0f} ')


def dumbbell(
    rows: Sequence[tuple[str, float, float]],
    *,
    title: str,
    before: str,
    after: str,
    fmt: Format,
    refs: Sequence[Ref] = (),
    label_w: float = 190,
) -> str:
    """Before and after per row, sorted by the later value, largest first."""
    rows = sorted(rows, key=lambda r: r[2], reverse=True)
    label_w = _label_width([r[0] for r in rows], label_w)
    top = _nice_max(max(max(r[1], r[2]) for r in rows))
    column = WIDTH - 8  # right edge of the value column
    x0, x1 = label_w, WIDTH - 72
    plot_top = TOP + 18  # extra room for the legend
    plot_bottom = plot_top + ROW * len(rows)

    def x(v: float) -> float:
        return x0 + (x1 - x0) * v / top

    body = [
        f'<g class="legend" transform="translate({x0},14)">'
        f'<circle class="dot-before" cx="5" cy="0" r="5"/><text x="16" y="4">{_esc(before)}</text>'
        f'<circle class="dot-after" cx="76" cy="0" r="5"/><text x="87" y="4">{_esc(after)}</text></g>',
        f'<text class="col-head" x="{column}" y="{plot_top - 12}" text-anchor="end">{_esc(after)}</text>',
    ]
    body += _axis(x, top, plot_top, plot_bottom, fmt)
    body += _refs(refs, x, plot_top, plot_bottom)
    for i, (label, then, now) in enumerate(rows):
        y = plot_top + i * ROW + ROW / 2
        change = (now / then - 1) * 100 if then else 0.0
        tip = f"{label}: {fmt(then)} in {before}, {fmt(now)} in {after} ({change:+.0f}%)"
        body.append(
            f'<g class="row"><title>{_esc(tip)}</title>'
            f'<rect class="hit" x="0" y="{y - ROW / 2}" width="{WIDTH}" height="{ROW}"/>'
            f'<text class="label" x="{x0 - 10}" y="{y + 4}" text-anchor="end">{_esc(label)}</text>'
            f'<line class="link" x1="{x(then):.1f}" x2="{x(now):.1f}" y1="{y}" y2="{y}"/>'
            f'<circle class="dot-before" cx="{x(then):.1f}" cy="{y}" r="5"/>'
            f'<circle class="dot-after" cx="{x(now):.1f}" cy="{y}" r="5"/>'
            f'<text class="value" x="{column}" y="{y + 4}" text-anchor="end">{_esc(fmt(now))}</text></g>'
        )
    return _frame(title, plot_bottom + AXIS, body, label_w)


# ── The page's charts ────────────────────────────────────────────────────────
# Each pulls the same data as the example it sits beside, through undata itself.


def _pct(v: float) -> str:
    return f"{v:.0f}%"


def _num(v: float) -> str:
    return f"{v:,.0f}"


def _people(v: float) -> str:
    if v >= 1e6:
        return f"{v / 1e6:.1f}M"
    if v >= 1e3:
        return f"{v / 1e3:.0f}K"
    return f"{v:.0f}"


def _multiples(panels: list[tuple[str, str]], caption: str) -> str:
    cells = "".join(
        f'<div class="panel"><p class="panel-title">{_esc(t)}</p>{svg}</div>' for t, svg in panels
    )
    return f'<div class="multiples">{cells}</div><figcaption>{_esc(caption)}</figcaption>'


def _single(svg: str, caption: str) -> str:
    return f'<div class="scroll">{svg}</div><figcaption>{_esc(caption)}</figcaption>'


def render_chart(number: str) -> str:
    """Return the HTML for the chart that belongs to example ``number``."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", un.UNDataWarning)
        if number == "01":
            sahel = ["Chad", "Niger", "Mali", "Burkina Faso", "Mauritania", "Sudan"]
            measures = [
                ("undata/sdg/EG_ACS_ELEC", "Access to electricity", _pct),
                ("undata/unicef/CME_MR.AGE--Y0T4", "Under-5 deaths per 1,000 live births", _num),
                ("undata/sdg/SE_TOT_CPLR.EDUCATION_LEVEL--ISCED11_1", "Primary completion", _pct),
            ]
            table = un.latest([m[0] for m in measures], sahel)
            panels = []
            for indicator, title, fmt in measures:
                part = table[table["indicator"] == indicator]
                rows = [(r.country, float(r.value), f"({r.year})") for r in part.itertuples()]
                panels.append(
                    (
                        title,
                        bars(
                            rows,
                            title=f"{title}, Sahel",
                            fmt=fmt,
                            highlight=["Chad"],
                            label_w=96,
                            width=320,
                        ),
                    )
                )
            return _multiples(
                panels, "Chad in green. Latest year for each country; hover a bar for its year."
            )
        if number == "02":
            mmr = "undata/sdg/SH_STA_MORT.SEX--F"
            wide = un.get(mmr, "Southern Asia", years=[2015, 2023]).pivot(
                index="country", columns="year", values="value"
            )
            rows = [(c, float(r[2015]), float(r[2023])) for c, r in wide.iterrows()]
            svg = dumbbell(
                rows,
                title="Maternal deaths per 100,000 live births, Southern Asia, 2015 and 2023",
                before="2015",
                after="2023",
                fmt=_num,
                refs=[Ref(70, "70")],
            )
            return _single(
                svg,
                "Maternal deaths per 100,000 live births. The dashed line marks 70, the level Target 3.1 sets for the world.",
            )
        if number == "03":
            table = un.latest("undata/sdg/SG_GEN_PARL.SEX--F", "Eastern Africa")
            rows = [(r.country, float(r.value), f"({r.year})") for r in table.itertuples()]
            parity = [r[0] for r in rows if r[1] >= 50]
            svg = bars(
                rows,
                title="Share of parliamentary seats held by women, Eastern Africa",
                fmt=_pct,
                highlight=parity,
                refs=[Ref(30, "30%"), Ref(50, "parity")],
            )
            return _single(
                svg,
                "Share of seats held by women, latest year. The dashed lines mark 30% and parity; past parity in green.",
            )
        if number == "04":
            number_id, rate_id = "undata/unicef/MG_RFGS_CNTRY_ORIGIN", "undata/sdg/SM_POP_REFG_OR"
            table = un.latest([number_id, rate_id], ["Eastern Africa", "Sudan"])
            panels = []
            for indicator, title, fmt in [
                (number_id, "Refugees, by country of origin", _people),
                (rate_id, "Refugees per 100,000 people", _num),
            ]:
                part = table[table["indicator"] == indicator].nlargest(6, "value")
                rows = [(r.country, float(r.value), f"({r.year})") for r in part.itertuples()]
                panels.append(
                    (
                        title,
                        bars(
                            rows,
                            title=title,
                            fmt=fmt,
                            highlight=["South Sudan"],
                            label_w=96,
                            width=320,
                        ),
                    )
                )
            return _multiples(
                panels,
                "Two measures, two charts: never two scales on one axis. South Sudan in green.",
            )
    return ""
