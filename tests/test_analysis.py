"""The 0.3 analyses, their charts, and the shared style, against the fake platform."""

from __future__ import annotations

import math
import warnings
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import pandas as pd
import pytest

import undata as un
from undata import analysis
from undata.analysis import (
    _GROWTH_BANDS,
    _RATIO_BANDS,
    INSUFFICIENT,
    MARGINAL,
    MODERATE,
    ON_TRACK,
    REGRESSION,
    STAGNATION,
    _assess,
    _score,
    cagr,
)

from .fake_api import ELEC, MMR, TOTN, FakeAPI


@pytest.fixture(autouse=True)
def agg_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MPLBACKEND", "Agg")


@contextmanager
def quiet() -> Iterator[None]:
    """Data-quality warnings are tested elsewhere; here they would only be noise."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", un.UNDataWarning)
        yield


def all_text(fig: object) -> str:
    from matplotlib.text import Text

    return " ".join(t.get_text() for t in fig.findobj(Text))  # type: ignore[attr-defined]


# ── The UNSD progress method ─────────────────────────────────────────────


def test_cagr_matches_the_formula_and_is_undefined_at_zero() -> None:
    assert cagr(100, 121, 2) == pytest.approx(0.1)
    assert cagr(0, 5, 3) is None
    assert cagr(5, 0, 3) is None
    assert cagr(5, 6, 0) is None


@pytest.mark.parametrize(
    ("ratio", "status", "score"),
    [
        (2.0, ON_TRACK, 5.0),  # clipped at the note's 1.5
        (1.5, ON_TRACK, 5.0),
        (0.95, ON_TRACK, 4.0),
        (0.725, MODERATE, 3.5),
        (0.5, MODERATE, 3.0),
        (0.3, MARGINAL, 2.5),
        (0.05, STAGNATION, 1.5),
        (0.0, STAGNATION, 1.0),
        (-0.25, REGRESSION, 0.5),
        (-3.0, REGRESSION, 0.0),  # clipped at -0.5
    ],
)
def test_ratio_bands_and_scores_follow_the_note(ratio: float, status: str, score: float) -> None:
    found, points = _score(ratio, _RATIO_BANDS)
    assert found == status
    assert points == pytest.approx(score)


def test_growth_bands_mirror_when_lower_is_better() -> None:
    assert _score(0.03, _GROWTH_BANDS)[0] == ON_TRACK
    assert _score(-0.03, _GROWTH_BANDS, mirrored=True)[0] == ON_TRACK
    assert _score(0.03, _GROWTH_BANDS, mirrored=True)[0] == REGRESSION
    assert _score(0.015, _GROWTH_BANDS)[0] == MODERATE
    assert _score(0.001, _GROWTH_BANDS)[0] == STAGNATION


def test_assess_projects_to_2030_and_compares_with_the_required_change() -> None:
    out = _assess(2015, 400, 2023, 300, better="lower", target=70, target_year=2030)
    rate = (300 / 400) ** (1 / 8) - 1
    projected = 300 * (1 + rate) ** 7
    assert out["cagr_pct"] == pytest.approx(rate * 100)
    assert out["projected"] == pytest.approx(projected)
    assert out["ratio"] == pytest.approx((projected - 400) / (70 - 400))  # 0.506
    assert out["status"] == MODERATE
    slower = _assess(2015, 400, 2023, 360, better="lower", target=70, target_year=2030)
    assert slower["status"] == MARGINAL


def test_assess_handles_targets_met_at_baseline_and_too_little_data() -> None:
    met = _assess(2015, 50, 2023, 40, better="lower", target=70, target_year=2030)
    lost = _assess(2015, 50, 2023, 90, better="lower", target=70, target_year=2030)
    once = _assess(2023, 50, 2023, 50, better="lower", target=70, target_year=2030)
    zero = _assess(2015, 0, 2023, 10, better="higher", target=None, target_year=2030)

    assert (met["status"], met["score"]) == (ON_TRACK, 5.0)
    assert (lost["status"], lost["score"]) == (REGRESSION, 0.0)
    assert once["status"] == INSUFFICIENT
    assert zero["status"] == INSUFFICIENT


def test_progress_assesses_each_country_and_says_how(fake: FakeAPI) -> None:
    with quiet():
        table = un.progress(MMR, ["Bangladesh", "Nepal"], better="lower", target=70)

    assert list(table.columns) == analysis.PROGRESS_COLUMNS
    bgd = table.set_index("country").loc["Bangladesh"]
    assert (bgd["baseline_year"], bgd["latest_year"]) == (2019, 2023)  # no 2015 value
    rate = (115.1 / 160) ** (1 / 4) - 1
    assert bgd["cagr_pct"] == pytest.approx(rate * 100)
    assert table.attrs["method"]
    assert sum(table.attrs["summary"].values()) == 2
    assert "Bangladesh" in un.describe(table) or un.describe(table)


def test_progress_without_a_target_uses_growth_rates(fake: FakeAPI) -> None:
    with quiet():
        table = un.progress(ELEC, ["Bangladesh"], better="higher")

    row = table.iloc[0]
    assert math.isnan(row["ratio"])
    assert row["status"] in un.STATUSES


# ── The other analyses ───────────────────────────────────────────────────


def test_trend_measures_change_since_a_baseline(fake: FakeAPI, tmp_path: Path) -> None:
    with quiet():
        table = un.trend(MMR, ["Bangladesh", "Nepal"], since=2019)

    assert set(table["country"]) == {"Bangladesh", "Nepal"}
    un.chart(table, tmp_path / "trend.png")
    assert (tmp_path / "trend.png").stat().st_size > 1000


def test_gap_compares_two_groups_in_the_same_year(fake: FakeAPI, tmp_path: Path) -> None:
    with quiet():
        table = un.gap(TOTN, ["Bangladesh"], by="sex")

    row = table.iloc[0]
    assert row["ratio"] == pytest.approx(4 / 9)
    assert table.attrs["gap"]["by"] == "sex"
    fig = un.chart(table, tmp_path / "gap.png")
    assert "Female" in all_text(fig)


def test_gap_explains_a_breakdown_the_indicator_lacks(fake: FakeAPI) -> None:
    with pytest.raises(ValueError, match="has no breakdown by 'wealth quantile'"):
        un.gap(MMR, ["Bangladesh"], by="wealth quantile")


def test_profile_places_a_country_beside_its_region_and_the_world(
    fake: FakeAPI, tmp_path: Path
) -> None:
    with quiet():
        table = un.profile("Bangladesh", [MMR, ELEC])

    mmr = table.set_index("indicator").loc[MMR]
    assert mmr["value"] == pytest.approx(115.1)
    assert mmr["world_value"] == pytest.approx(197.3)
    assert table.attrs["profile"]["region"] == "Southern Asia"
    fig = un.chart(table, tmp_path / "profile.png")
    assert "highest of 2 in Southern Asia" in all_text(fig)


def test_benchmark_compares_published_group_totals(fake: FakeAPI, tmp_path: Path) -> None:
    with quiet():
        table = un.benchmark(MMR)

    assert "World" in set(table["place"])
    un.chart(table, tmp_path / "benchmark.png")


def test_availability_grids_the_latest_year_per_indicator(fake: FakeAPI, tmp_path: Path) -> None:
    with quiet():
        grid = un.availability([MMR, ELEC], ["Bangladesh", "Nepal"])

    assert list(grid.loc["Nepal"]) == [2022, 2018]
    fig = un.chart(grid, tmp_path / "grid.png")
    assert "how recently" in all_text(fig)


# ── Charts ───────────────────────────────────────────────────────────────


def test_every_chart_carries_its_source_and_saves(fake: FakeAPI, tmp_path: Path) -> None:
    with quiet():
        tables = {
            "progress": un.progress(MMR, ["Bangladesh", "Nepal"], better="lower", target=70),
            "bar": un.latest(ELEC, ["Bangladesh", "Nepal"]),
            "line": un.get(MMR, "Bangladesh"),
            "map": un.latest(MMR, ["Bangladesh", "Nepal"]),
            "scatter": un.compare([MMR, ELEC], ["Bangladesh", "Nepal"]),
            "dumbbell": un.change(MMR, ["Bangladesh", "Nepal"], 2019, 2023),
        }
    for kind, table in tables.items():
        fig = un.chart(
            table, tmp_path / f"{kind}.png", kind="map" if kind == "map" else "auto", note="A note."
        )
        text = all_text(fig)
        assert "Source:" in text, kind
        assert "A note." in text, kind
        assert (tmp_path / f"{kind}.png").stat().st_size > 1000, kind


def test_charts_keep_long_titles_inside_the_figure(fake: FakeAPI) -> None:
    with quiet():
        table = un.latest(ELEC, ["Bangladesh", "Nepal"])
    long_title = "A very long title that goes on " * 6
    fig = un.chart(table, title=long_title, context="slides")
    from matplotlib.text import Text

    title = next(t.get_text() for t in fig.findobj(Text) if "very long" in t.get_text())
    assert "\n" in title


def test_chart_draws_small_multiples_when_lines_would_be_too_many(no_display: None) -> None:
    many = pd.DataFrame(
        {
            "country": [f"C{i}" for i in range(7) for _ in range(2)],
            "year": [2020, 2021] * 7,
            "value": 1.0,
            "indicator_name": "x",
            "unit": "%",
            "source": "s",
        }
    )
    with pytest.raises(ValueError, match="too many lines"):
        un.chart(many, kind="line")
    fig = un.chart(many)
    assert len(fig.axes) >= 7


@pytest.fixture
def no_display() -> None:
    return None


def test_interactive_charts_cover_each_kind(fake: FakeAPI, tmp_path: Path) -> None:
    pytest.importorskip("plotly")
    with quiet():
        tables = [
            un.progress(MMR, ["Bangladesh", "Nepal"], better="lower", target=70),
            un.latest(ELEC, ["Bangladesh", "Nepal"]),
            un.get(MMR, ["Bangladesh", "Nepal"]),
            un.compare([MMR, ELEC], ["Bangladesh", "Nepal"]),
            un.change(MMR, ["Bangladesh", "Nepal"], 2019, 2023),
            un.availability([MMR, ELEC], ["Bangladesh", "Nepal"]),
        ]
    for i, table in enumerate(tables):
        figure = un.chart(table, tmp_path / f"{i}.html", interactive=True, highlight="Nepal")
        assert figure.data, i
        assert "Source:" in figure.layout.annotations[0].text
        assert (tmp_path / f"{i}.html").read_text().count("Plotly.newPlot") == 1
    with quiet():
        mapped = un.latest(MMR, ["Bangladesh", "Nepal"])
    assert un.chart(mapped, kind="map", interactive=True).data
    with pytest.raises(ValueError, match="Interactive charts cover"):
        un.chart(mapped, kind="profile", interactive=True)


# ── Style and palettes ───────────────────────────────────────────────────


def test_style_sets_matplotlib_defaults_and_palettes_are_exposed() -> None:
    import matplotlib as mpl

    with mpl.rc_context():
        un.style("slides")
        assert mpl.rcParams["font.size"] == 13.0
        assert mpl.rcParams["axes.spines.top"] is False
        assert mpl.rcParams["savefig.dpi"] == 300
    assert un.palette() == list(un.style.__globals__["CATEGORICAL"])
    assert len(un.palette("status")) == len(un.STATUSES)
    with pytest.raises(ValueError, match="Choose"):
        un.palette("rainbow")  # type: ignore[arg-type]


# ── Tables built by undata still combine with pandas ─────────────────────


def test_tables_with_attached_long_tables_concatenate(fake: FakeAPI) -> None:
    with quiet():
        a = un.wide(un.get(MMR, "Bangladesh"))
        b = un.wide(un.get(MMR, "Nepal"))
        p = un.progress(MMR, ["Bangladesh"], better="lower", target=70)

    both = pd.concat([a, b])
    assert len(both) == len(a) + len(b)
    assert len(pd.concat([p, p])) == 2
    assert un.cite(a)


# ── Sentences ────────────────────────────────────────────────────────────


def test_describe_writes_the_finding_of_each_analysis(fake: FakeAPI) -> None:
    with quiet():
        progress = un.progress(MMR, ["Bangladesh", "Nepal"], better="lower", target=70)
        growth = un.progress(ELEC, ["Bangladesh"], better="higher")
        gap = un.gap(TOTN, ["Bangladesh"], by="sex")
        profile = un.profile("Bangladesh", [MMR, ELEC])

    text = un.describe(progress)
    assert text.startswith("Maternal mortality ratio, 2 countries.")
    assert "compared with the target of 70.0" in text
    assert "Technical Note for Progress Assessment" in text
    assert "as no target was given" in un.describe(growth)
    assert "the widest gap is in Bangladesh, 4.00 against 9.00 in 2023" in un.describe(gap)
    assert "No country is within 0.97-1.03 of parity." in un.describe(gap)
    lines = un.describe(profile).splitlines()
    assert lines[0] == "Bangladesh, latest values beside Southern Asia and the world:"
    assert "world 197" in lines[1]


@pytest.mark.parametrize(
    ("rank", "out_of", "words"),
    [
        (1, 9, "highest of 9"),
        (9, 9, "lowest of 9"),
        (2, 9, "2nd highest of 9"),
        (3, 9, "3rd highest of 9"),
        (11, 20, "11th highest of 20"),
        (1, 1, "highest of 1"),
    ],
)
def test_ranks_read_the_same_for_good_and_bad(rank: int, out_of: int, words: str) -> None:
    assert analysis.ordinal(rank, out_of) == words
