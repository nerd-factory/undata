"""Interactive versions of undata's charts, with Plotly: hover, zoom, and HTML export.

Reached through ``un.chart(table, interactive=True)``. The same palettes, titles and
source captions as the static charts, so the two can sit in one report and one site.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from ._long import long_of
from .chart import (
    SHORT_STATUS,
    _caption,
    _latest_per_country,
    _one_indicator,
    _short,
    _tiles,
    _unit,
)
from .style import ACCENT, CATEGORICAL, FONT, GRID, INK, MUTED, SEQUENTIAL, SOFT, STATUS


def _go() -> Any:
    try:
        import plotly.graph_objects as go  # noqa: PLC0415 — an optional dependency
    except ImportError as exc:  # pragma: no cover - exercised without plotly
        raise ImportError(
            'Interactive charts need plotly: pip install "undata[interactive]"'
        ) from exc
    return go


def _layout(fig: Any, title: str, subtitle: str, caption: str, height: int) -> Any:
    fig.update_layout(
        title={
            "text": f"<b>{title}</b><br><span style='font-size:13px;color:{SOFT}'>{subtitle}</span>",
            "x": 0.01,
            "xanchor": "left",
        },
        font={"family": ", ".join(FONT), "color": INK, "size": 13},
        plot_bgcolor="white",
        paper_bgcolor="white",
        height=height,
        margin={"l": fig.layout.margin.l or 10, "r": 30, "t": 110, "b": 90},
        legend={
            "orientation": "h",
            "x": 0,
            "xanchor": "left",
            "y": 1.0,
            "yanchor": "bottom",
            "entrywidth": 125,  # fixed, so fallback fonts cannot make entries overlap
        },
        hoverlabel={"bgcolor": "white", "font_size": 12},
        annotations=[
            {
                "text": caption.replace("\n", "<br>"),
                "xref": "paper",
                "yref": "paper",
                "x": 0,
                "y": -0.12,
                "showarrow": False,
                "xanchor": "left",
                "yanchor": "top",
                "align": "left",
                "font": {"size": 10, "color": SOFT},
            }
        ],
    )
    fig.update_xaxes(gridcolor=GRID, zeroline=False, linecolor=GRID)
    fig.update_yaxes(gridcolor=GRID, zeroline=False, automargin=True)
    return fig


def _room_for(fig: Any, labels: pd.Series) -> None:
    """A left margin wide enough for the longest category label."""
    longest = int(labels.astype(str).str.len().max()) if len(labels) else 0
    fig.update_layout(margin={"l": 20 + 7 * longest})


def draw(table: pd.DataFrame, kind: str, *, title: str | None, highlight: set[str]) -> Any:
    """Draw ``kind`` as a Plotly figure."""
    go = _go()
    long = long_of(table)
    caption = _caption(table, long, None)
    if kind == "progress":
        rows = table.iloc[::-1]
        fig = go.Figure()
        fig.add_trace(
            go.Scatter(
                x=rows["baseline_value"],
                y=rows["country"],
                mode="markers",
                name="baseline",
                marker={"color": MUTED, "size": 8},
                customdata=rows[["baseline_year"]],
                hovertemplate="%{y}: %{x:,.3~r} in %{customdata[0]}<extra>baseline</extra>",
            )
        )
        if rows["projected"].notna().any():
            fig.add_trace(
                go.Scatter(
                    x=rows["projected"],
                    y=rows["country"],
                    mode="markers",
                    name="projected 2030",
                    marker={"color": "white", "size": 9, "line": {"color": INK, "width": 1.5}},
                    hovertemplate="%{y}: %{x:,.3~r} projected<extra></extra>",
                )
            )
        for status, colour in STATUS.items():
            part = rows[rows["status"] == status]
            if part.empty:
                continue
            fig.add_trace(
                go.Scatter(
                    x=part["latest_value"],
                    y=part["country"],
                    mode="markers",
                    name=SHORT_STATUS[status],
                    marker={"color": colour, "size": 12, "line": {"color": "white", "width": 1}},
                    customdata=part[["baseline_year", "baseline_value", "latest_year", "score"]],
                    hovertemplate="%{y}: %{x:,.3~r} in %{customdata[2]}<br>baseline %{customdata[1]:,.3~r} "
                    "in %{customdata[0]}<br>score %{customdata[3]:.2f}<extra>"
                    + SHORT_STATUS[status]
                    + "</extra>",
                )
            )
        target = table.attrs.get("assessment", {}).get("target")
        if target is not None:
            fig.add_vline(
                x=target, line_dash="dash", line_color=INK, annotation_text=f"target {target}"
            )
        name = (
            _short(str(rows["indicator_name"].dropna().iloc[0]))
            if rows["indicator_name"].notna().any()
            else ""
        )
        fig.update_yaxes(categoryorder="array", categoryarray=list(rows["country"]))
        _room_for(fig, rows["country"])
        return _layout(
            fig, title or f"Progress on {name}", _unit(long), caption, 180 + 26 * len(rows)
        )
    if kind == "heatmap":
        fig = go.Figure(
            go.Heatmap(
                z=table.astype("float").to_numpy(),
                x=[_short(str(c)) for c in table.columns],
                y=list(table.index),
                colorscale=[[i / (len(SEQUENTIAL) - 1), c] for i, c in enumerate(SEQUENTIAL)],
                hovertemplate="%{y}<br>%{x}: latest %{z}<extra></extra>",
                xgap=3,
                ygap=3,
            )
        )
        fig.update_yaxes(autorange="reversed")
        return _layout(
            fig,
            title or "Which countries report what, and how recently",
            "Year of the latest value",
            caption,
            160 + 24 * len(table),
        )
    if kind == "scatter":
        labels = [
            c
            for c in table.columns
            if c not in ("country", "iso3") and not str(c).endswith(" year")
        ]
        x, y = labels[0], labels[1]
        both = table.dropna(subset=[x, y])
        fig = go.Figure(
            go.Scatter(
                x=both[x],
                y=both[y],
                mode="markers+text" if len(both) <= 25 else "markers",  # noqa: PLR2004
                text=both["country"],
                textposition="top right",
                marker={
                    "color": [
                        ACCENT if not highlight or c in highlight else MUTED
                        for c in both["country"]
                    ],
                    "size": 10,
                },
                hovertemplate="%{text}<br>"
                + x
                + ": %{x:,.3~r}<br>"
                + y
                + ": %{y:,.3~r}<extra></extra>",
            )
        )
        fig.update_xaxes(title=x)
        fig.update_yaxes(title=y)
        return _layout(
            fig, title or f"{x} and {y}", f"{len(both)} countries with both", caption, 520
        )
    name = _short(_one_indicator(long))
    if kind in ("line", "facets"):
        fig = go.Figure()
        for i, country in enumerate(sorted(set(long["country"]))):
            rows = long[long["country"] == country].sort_values("year")
            colour = (
                CATEGORICAL[i % len(CATEGORICAL)]
                if not highlight or country in highlight
                else MUTED
            )
            fig.add_trace(
                go.Scatter(
                    x=rows["year"],
                    y=rows["value"],
                    name=country,
                    mode="lines+markers",
                    line={"color": colour, "width": 2},
                    marker={"size": 5},
                    hovertemplate=country + " %{x}: %{y:,.3~r}<extra></extra>",
                )
            )
        return _layout(fig, title or name, _unit(long), caption, 480)
    if kind == "map":
        rows = _latest_per_country(long)
        tiles = _tiles()
        placed = rows[rows["iso3"].isin(tiles)]
        fig = go.Figure(
            go.Scatter(
                x=[tiles[i][1] for i in placed["iso3"]],
                y=[tiles[i][0] for i in placed["iso3"]],
                mode="markers+text",
                text=placed["iso3"],
                textfont={"size": 8, "color": "white"},
                marker={
                    "symbol": "square",
                    "size": 22,
                    "color": placed["value"],
                    "colorscale": [
                        [i / (len(SEQUENTIAL) - 1), c] for i, c in enumerate(SEQUENTIAL)
                    ],
                    "colorbar": {"thickness": 10, "len": 0.6},
                },
                customdata=placed[["country", "value", "year"]],
                hovertemplate="%{customdata[0]}: %{customdata[1]:,.3~r} (%{customdata[2]})<extra></extra>",
            )
        )
        fig.update_xaxes(visible=False)
        fig.update_yaxes(visible=False, autorange="reversed", scaleanchor="x")
        return _layout(fig, title or name, _unit(long) + ". One square per country.", caption, 560)
    if kind in ("bar", "dumbbell", "slope"):
        if "start_value" in table.columns or "baseline_value" in table.columns:
            start, end = (
                ("start_value", "end_value")
                if "start_value" in table.columns
                else ("baseline_value", "latest_value")
            )
            label = "country" if "country" in table.columns else "place"
            rows = table.sort_values(end)
            fig = go.Figure()
            for _, row in rows.iterrows():
                fig.add_trace(
                    go.Scatter(
                        x=[row[start], row[end]],
                        y=[row[label]] * 2,
                        mode="lines",
                        line={"color": GRID, "width": 3},
                        showlegend=False,
                        hoverinfo="skip",
                    )
                )
            fig.add_trace(
                go.Scatter(
                    x=rows[start],
                    y=rows[label],
                    mode="markers",
                    name="start",
                    marker={"color": "white", "size": 10, "line": {"color": MUTED, "width": 2}},
                )
            )
            fig.add_trace(
                go.Scatter(
                    x=rows[end],
                    y=rows[label],
                    mode="markers",
                    name="latest",
                    marker={"color": ACCENT, "size": 11},
                )
            )
            _room_for(fig, rows[label])
            return _layout(fig, title or name, _unit(table), caption, 140 + 26 * len(rows))
        rows = _latest_per_country(long).sort_values("value")
        fig = go.Figure(
            go.Bar(
                x=rows["value"],
                y=rows["country"],
                orientation="h",
                marker={
                    "color": [
                        ACCENT if not highlight or c in highlight else MUTED
                        for c in rows["country"]
                    ]
                },
                customdata=rows[["year"]],
                hovertemplate="%{y}: %{x:,.3~r} (%{customdata[0]})<extra></extra>",
            )
        )
        _room_for(fig, rows["country"])
        return _layout(fig, title or name, _unit(long), caption, 140 + 24 * len(rows))
    raise ValueError(
        f'Interactive charts cover bar, line, map, heatmap, scatter, progress and dumbbell, not "{kind}".'
    )
