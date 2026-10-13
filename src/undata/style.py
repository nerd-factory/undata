"""The look of undata's charts, and of yours.

``un.style()`` sets matplotlib (and seaborn, if installed) to the same clean defaults
:func:`undata.chart` uses, so charts you draw yourself sit beside undata's without
looking different. The palettes are exposed too.

It is undata's own neutral style. It does not imitate the UN's visual identity: the
package is unofficial, and its charts should not look like official UN products.

Every palette here was checked with a colour-vision validator:

* ``CATEGORICAL`` - Okabe-Ito hues, ordered so neighbours differ most. Its closest
  pair needs labels as well as colour, which every undata chart gives lines.
* ``SEQUENTIAL`` - one blue, light to dark, for maps and heatmaps; passes the ordinal
  checks (one hue, lightness in order, visible steps, light end clear of white).
* ``STATUS`` - the five progress categories, on a good/warning/serious/critical
  palette. Status colours never carry meaning alone; charts label them too.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Final, Literal

__all__ = ["ACCENT", "CATEGORICAL", "MUTED", "SEQUENTIAL", "STATUS", "palette", "style"]

INK: Final = "#1F1F24"
SOFT: Final = "#5E5E66"  # secondary text: subtitles, notes, axis labels
FAINT: Final = "#8C8C94"  # tertiary text: source lines
GRID: Final = "#E6E6EA"
BASELINE: Final = "#B8B8C0"
ACCENT: Final = "#0072B2"
MUTED: Final = "#B4B4BC"
FONT: Final = [
    "Inter",
    "Source Sans 3",
    "Source Sans Pro",
    "Helvetica Neue",
    "Arial",
    "Liberation Sans",
    "DejaVu Sans",
]

CATEGORICAL: Final = ("#0072B2", "#D55E00", "#009E73", "#CC79A7", "#E69F00", "#56B4E9")
SEQUENTIAL: Final = ("#86B6EF", "#5598E7", "#256ABF", "#104281")

STATUS: Final[Mapping[str, str]] = {
    "On track or target met": "#0CA30C",
    "Moderate progress, but acceleration needed": "#7DCB7D",
    "Marginal progress, and significant acceleration needed": "#FAB219",
    "Stagnation": "#EC835A",
    "Regression": "#D03B3B",
    "Insufficient data": "#C4C4CA",
}

Context = Literal["report", "slides"]

#: Figure widths in inches: a report column, and a 16:9 slide.
WIDTH: Final[Mapping[str, float]] = {"report": 7.5, "slides": 12.0}
_TEXT: Final[Mapping[str, float]] = {"report": 9.0, "slides": 13.0}


def palette(name: Literal["categorical", "sequential", "status"] = "categorical") -> list[str]:
    """One of undata's checked palettes, as hex colours.

    Example:
        >>> import undata as un
        >>> un.palette("sequential")
        ['#86B6EF', '#5598E7', '#256ABF', '#104281']
    """
    if name == "categorical":
        return list(CATEGORICAL)
    if name == "sequential":
        return list(SEQUENTIAL)
    if name == "status":
        return list(STATUS.values())
    raise ValueError('Choose "categorical", "sequential" or "status".')


def rc(context: Context = "report") -> dict[str, Any]:
    """The matplotlib settings behind the style."""
    from cycler import cycler  # noqa: PLC0415 — comes with matplotlib, an optional dependency

    size = _TEXT[context]
    return {
        "font.family": "sans-serif",
        "font.sans-serif": FONT,
        "font.size": size,
        "text.color": INK,
        "axes.titlesize": size * 1.35,
        "axes.titleweight": "bold",
        "axes.titlelocation": "left",
        "axes.labelsize": size,
        "axes.labelcolor": SOFT,
        "axes.edgecolor": BASELINE,
        "axes.linewidth": 0.8,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.spines.left": False,
        "axes.grid": True,
        "axes.grid.axis": "y",
        "axes.axisbelow": True,
        "axes.prop_cycle": cycler(color=list(CATEGORICAL)),
        "grid.color": GRID,
        "grid.linewidth": 0.8,
        "xtick.color": SOFT,
        "ytick.color": SOFT,
        "xtick.labelsize": size * 0.9,
        "ytick.labelsize": size * 0.9,
        "xtick.major.size": 0,
        "ytick.major.size": 0,
        "legend.frameon": False,
        "legend.fontsize": size * 0.9,
        "lines.linewidth": 2.0,
        "lines.solid_capstyle": "round",
        "figure.facecolor": "white",
        "axes.facecolor": "white",
        "savefig.facecolor": "white",
        "savefig.bbox": "tight",
        "savefig.dpi": 300,
        "figure.dpi": 110,
        "svg.fonttype": "none",  # keep text as text in SVG, editable in Illustrator
        "pdf.fonttype": 42,  # embed TrueType, so PDFs stay editable and searchable
    }


def style(context: Context = "report") -> None:
    """Give matplotlib and seaborn charts undata's clean, report-ready defaults.

    Call it once at the top of a notebook. Charts you draw with matplotlib, pandas'
    ``.plot()`` or seaborn then share undata's fonts, colours, light grid and export
    settings (300 dpi PNG, editable SVG and PDF text).

    Args:
        context: ``"report"`` for documents, ``"slides"`` for presentations (larger
            text).

    Example:
        >>> import undata as un
        >>> un.style()  # doctest: +SKIP
        >>> import seaborn as sns  # doctest: +SKIP
        >>> sns.barplot(table, x="value", y="country")  # doctest: +SKIP
    """
    try:
        import matplotlib as mpl  # noqa: PLC0415 — an optional dependency
    except ImportError as exc:  # pragma: no cover - exercised without matplotlib
        raise ImportError('un.style() needs matplotlib: pip install "undata[charts]"') from exc
    settings = rc(context)
    try:
        import seaborn as sns  # noqa: PLC0415 — optional; styled when present

        sns.set_theme(style="whitegrid", palette=list(CATEGORICAL), rc=settings)
    except ImportError:
        pass
    params: Any = mpl.rcParams  # its stubs list the keys as literals; ours are plain str
    params.update(settings)
