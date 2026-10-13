"""The friendly API against the real platform.

The offline tests use a fake shaped like the real responses; these check the real
responses still have that shape, and that the built-in tables (regions, UN names)
still match what the platform holds.
"""

from __future__ import annotations

import csv
import importlib.util
import warnings
from pathlib import Path

import httpx
import pytest

import undata as un
from undata.indicators import names
from undata.places import m49

pytestmark = pytest.mark.live

MMR = "undata/sdg/SH_STA_MORT.SEX--F"


def test_the_shipped_m49_list_matches_the_un_statistics_division() -> None:
    """If this fails, the UN changed M49: run scripts/update_m49.py and release."""
    script = Path(__file__).resolve().parents[2] / "scripts" / "update_m49.py"
    spec = importlib.util.spec_from_file_location("update_m49", script)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    shipped_file = Path(__file__).resolve().parents[2] / "src" / "undata" / "m49.csv"
    shipped = list(csv.DictReader(shipped_file.read_text(encoding="utf-8").splitlines()))

    current = sorted(module.fetch(), key=lambda r: r["iso3"])

    assert current == shipped


def test_the_platform_holds_the_m49_countries() -> None:
    # The firewall refuses any GET that mentions these, so the name lookup skips them.
    ids = [f"country/{c.iso3}" for c in m49() if c.iso3 not in {"ESH", "GRC", "SVN"}]
    known: dict[str, str] = {}
    for start in range(0, len(ids), 50):
        known.update(names(ids[start : start + 50]))

    missing = sorted(set(ids) - set(known))
    assert len(missing) < 15, missing


def test_get_returns_real_values_with_sources() -> None:
    table = un.get(MMR, ["Bangladesh", "Viet Nam"], years=(2020, 2023))

    assert set(table["country"]) == {"Bangladesh", "Viet Nam"}
    assert set(table["year"]) == {2020, 2021, 2022, 2023}
    assert set(table["source"]) == {"SDG Global Database"}
    assert set(table["unit"]) == {"Count per 100,000 live births"}


def test_latest_for_a_region() -> None:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", un.UNDataWarning)
        table = un.latest("undata/sdg/EG_ACS_ELEC", "Southern Asia")

    assert "Iran (Islamic Republic of)" in set(table["country"])
    assert table["value"].between(0, 100).all()


def test_missing_data_is_reported_not_zeroed() -> None:
    with pytest.warns(un.MissingDataWarning, match="Norway"):
        table = un.get("undata/sdg/VC_DTH_TOTR", ["Norway", "Ukraine"])

    assert set(table["country"]) == {"Ukraine"}


def test_search_puts_a_maternal_mortality_ratio_first() -> None:
    top = un.search("maternal mortality").iloc[0]

    assert "Maternal mortality ratio" in top["name"]


def test_about() -> None:
    info = un.about(MMR)

    assert info.source == "SDG Global Database"
    assert info.first_year == "2000"


def test_sdg_walk_reaches_fetchable_series() -> None:
    assert len(un.sdg.goals()) == 17
    assert "16.1" in set(un.sdg.targets(16)["target"])
    assert "16.1.2" in set(un.sdg.indicators("16.1")["indicator"])
    assert "undata/sdg/VC_DTH_TOTR" in set(un.sdg.series("16.1.2")["indicator"])


def test_ask_flags_the_guessed_place() -> None:
    with pytest.warns(un.PlaceGuessedWarning):
        answer = un.ask("child mortality in Bengal")

    assert answer.place_was_guessed
    assert answer.place_id == "country/USA"


def test_latest_for_all_of_africa_survives_western_sahara() -> None:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", un.UNDataWarning)
        table = un.latest("undata/sdg/EG_ACS_ELEC", "Africa")

    assert len(table) >= 50


# ── 0.2 features against the real platform ─────────────────────────────────


@pytest.mark.parametrize("group", ["LDCs", "LLDCs", "SIDS"])
def test_un_groupings_have_members_and_an_official_total(group: str) -> None:
    assert len(un.places.expand(group)) > 25
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", un.UNDataWarning)
        total = un.totals(MMR, group, latest=True)
    assert len(total) == 1
    assert total["source"].iloc[0] == "SDG Global Database"


def test_world_total_is_the_published_figure() -> None:
    world = un.totals(MMR, "World", years=2023)

    assert 150 < world["value"].iloc[0] < 250


def test_sdg_numbers_resolve_or_list_their_series() -> None:
    assert set(un.get("3.1.1", "Bangladesh", years=2023)["indicator"]) == {MMR}
    with pytest.raises(un.AmbiguousIndicatorError):
        un.get("16.1.2", "Mali")


def test_breakdowns_and_by() -> None:
    assert {"sex", "age"} <= set(un.breakdowns("undata/sdg/VC_DTH_TOTN").columns)
    table = un.get("undata/unicef/CME_MR.AGE--Y0T4", "Chad", years=2024, by="sex")
    assert {"Female", "Male"} <= set(table["sex"])


def test_about_links_the_sdg_metadata() -> None:
    info = un.about(MMR)

    assert info.sdg_indicator == "3.1.1"
    assert info.metadata.endswith("Metadata-03-01-01.pdf")
    assert httpx.head(info.metadata, follow_redirects=True, timeout=30).status_code == 200


def test_search_shows_coverage() -> None:
    table = un.search("access to electricity", limit=3)

    assert table["places"].iloc[0] > 100
    assert table["years"].iloc[0]


def test_change_and_compare() -> None:
    moved = un.change(MMR, "Southern Asia", 2015, 2023)
    assert (moved["change"] < 0).all()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", un.UNDataWarning)
        both = un.compare(
            {"conflict": "undata/sdg/VC_DTH_TOTR", "homicide": "undata/sdg/VC_IHR_PSRC"}, "World"
        )
    assert 0 < len(both.attrs["coverage"]["all"]) < 40
