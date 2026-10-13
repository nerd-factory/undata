"""The friendly API against the real platform.

The offline tests use a fake shaped like the real responses; these check the real
responses still have that shape, and that the built-in tables (regions, UN names)
still match what the platform holds.
"""

from __future__ import annotations

import warnings

import pytest

import undata as un
from undata.places import REGIONS, UN_NAMES, _members, _platform_names, resolve

pytestmark = pytest.mark.live

MMR = "undata/sdg/SH_STA_MORT.SEX--F"


def test_every_built_in_region_has_countries() -> None:
    empty = [name for name in REGIONS.values() if not _members(resolve(name))]

    assert empty == []


def test_every_un_name_maps_to_a_country_the_platform_has() -> None:
    known = {dcid.removeprefix("country/") for dcid in _platform_names()}

    assert set(UN_NAMES) - known == set()


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
