"""The 0.3 analyses and charts against the real platform."""

from __future__ import annotations

import warnings
from collections.abc import Iterator
from pathlib import Path

import pytest

import undata as un

pytestmark = pytest.mark.live

MMR = "undata/sdg/SH_STA_MORT.SEX--F"
COMPLETION = "undata/sdg/SE_TOT_CPLR.EDUCATION_LEVEL--ISCED11_1"


@pytest.fixture(autouse=True)
def quiet(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setenv("MPLBACKEND", "Agg")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", un.UNDataWarning)
        yield


def test_progress_assesses_every_ldc(tmp_path: Path) -> None:
    table = un.progress("3.1.1", "LDCs", better="lower", target=70)

    assert len(table) == 44  # the UN's current LDC list
    assert set(table["status"].astype(str)) <= set(un.STATUSES)
    assert (table["baseline_year"].dropna() >= 2015).all()
    un.chart(table, tmp_path / "progress.png")


def test_profile_puts_chad_in_middle_africa(tmp_path: Path) -> None:
    table = un.profile("Chad", [MMR, COMPLETION])

    assert table.attrs["profile"]["region"] == "Middle Africa"
    assert table["world_value"].notna().all()
    un.chart(table, tmp_path / "profile.png")


def test_gap_finds_the_rural_urban_gap_in_chad(tmp_path: Path) -> None:
    table = un.gap(COMPLETION, ["Chad", "Bangladesh"], by="urbanization")

    chad = table.set_index("country").loc["Chad"]
    assert chad["ratio"] < 1
    un.chart(table, tmp_path / "gap.png")


def test_benchmark_availability_and_the_tile_map(tmp_path: Path) -> None:
    groups = un.benchmark(MMR)
    grid = un.availability([MMR, COMPLETION], "Western Africa")
    africa = un.latest(MMR, "Africa", within=10)

    assert "World" in set(groups["place"])
    assert len(grid) == 17  # Western Africa in M49, Saint Helena included
    un.chart(groups, tmp_path / "groups.png")
    un.chart(grid, tmp_path / "grid.png")
    un.chart(africa, tmp_path / "map.png", kind="map")
