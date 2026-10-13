from __future__ import annotations

import pandas as pd
import pytest

import undata as un
from undata.data import COLUMNS

from .fake_api import ELEC, MMR, RAW, FakeAPI


def test_get_returns_a_tidy_table_with_sources(fake: FakeAPI) -> None:
    table = un.get(MMR, "Bangladesh")

    assert list(table.columns) == COLUMNS
    assert list(table["year"]) == [2019, 2020, 2021, 2022, 2023]
    first = table.iloc[-1]
    assert first["country"] == "Bangladesh"
    assert first["iso3"] == "BGD"
    assert first["value"] == pytest.approx(115.1)
    assert first["unit"] == "Count per 100,000 live births"
    assert first["indicator_name"] == "Maternal mortality ratio [Sex=Female]"
    assert first["source"] == "SDG Global Database"
    assert first["source_url"] == "https://unstats.un.org/sdgs/dataportal"
    assert table.attrs["missing"] == []


@pytest.mark.parametrize(
    ("years", "expected"),
    [
        (2021, [2021]),
        ((2020, 2022), [2020, 2021, 2022]),
        ([2019, 2023], [2019, 2023]),
        (range(2022, 2030), [2022, 2023]),
    ],
)
def test_get_filters_years(fake: FakeAPI, years: un.data.Years, expected: list[int]) -> None:
    assert list(un.get(MMR, "BGD", years=years)["year"]) == expected


def test_backwards_years_are_explained(fake: FakeAPI) -> None:
    with pytest.raises(ValueError, match="runs backwards"):
        un.get(MMR, "BGD", years=(2023, 2020))


def test_missing_countries_are_named_and_never_zero(fake: FakeAPI) -> None:
    with pytest.warns(un.MissingDataWarning, match="No data for 1 of 3") as caught:
        table = un.get(MMR, ["Bangladesh", "Nepal", "Norway"])

    assert "Maternal mortality ratio [Sex=Female]: Norway" in str(caught[0].message)
    assert "Norway" not in set(table["country"])
    assert table.attrs["missing"] == [
        {"country": "Norway", "indicator_name": "Maternal mortality ratio [Sex=Female]"}
    ]


def test_a_year_filter_that_leaves_nothing_counts_as_missing(fake: FakeAPI) -> None:
    with pytest.warns(un.MissingDataWarning, match="Nepal"):
        table = un.get(MMR, ["Bangladesh", "Nepal"], years=2019)

    assert list(table["country"]) == ["Bangladesh"]


def test_long_missing_lists_are_shortened(fake: FakeAPI) -> None:
    with pytest.warns(un.MissingDataWarning, match="and 1 more"):
        un.get(ELEC, "World")


def test_get_accepts_regions_and_sends_them_in_chunks(
    fake: FakeAPI, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("undata.data._CHUNK", 1)

    table = un.get(MMR, "Southern Asia")

    assert set(table["country"]) == {"Bangladesh", "Nepal"}
    assert fake.calls["series"] == 2


def test_get_rejects_a_phrase_before_fetching_anything(fake: FakeAPI) -> None:
    with pytest.raises(un.IndicatorNotFoundError):
        un.get("maternal mortality", "Nepal")

    assert fake.calls["series"] == 0


def test_latest_returns_one_row_per_country_and_says_which_year(fake: FakeAPI) -> None:
    with pytest.warns(un.MixedYearsWarning, match="2018 to 2024"):
        table = un.latest(ELEC, ["Bangladesh", "Nepal"])

    assert list(table.columns) == COLUMNS
    assert list(zip(table["country"], table["year"], strict=True)) == [
        ("Bangladesh", 2024),
        ("Nepal", 2018),
    ]
    assert set(table["source"]) == {"UN_SDG (Data Commons copy)"}
    assert set(table["unit"]) == {"Percent"}


def test_latest_takes_each_countrys_most_recent_point(fake: FakeAPI) -> None:
    table = un.latest(MMR, "Bangladesh")

    assert list(table["year"]) == [2023]
    assert table["value"].iloc[0] == pytest.approx(115.1)


def test_latest_translates_a_unit_id_and_warns_about_gaps(fake: FakeAPI) -> None:
    with pytest.warns(un.MissingDataWarning, match="Nepal"):
        table = un.latest(RAW, ["Bangladesh", "Nepal"])

    assert table.iloc[0]["unit"] == "Count per 100,000 live births"
    assert table.attrs["missing"][0]["country"] == "Nepal"


def test_latest_uses_post_so_western_sahara_cannot_trip_the_firewall(fake: FakeAPI) -> None:
    with pytest.warns(un.MixedYearsWarning):
        un.latest(ELEC, "Southern Asia")

    assert fake.calls["series"] == 1


def test_an_empty_result_is_still_a_well_formed_table(fake: FakeAPI) -> None:
    with pytest.warns(un.MissingDataWarning):
        table = un.get(MMR, "Norway")

    assert table.empty
    assert list(table.columns) == COLUMNS
    assert table["year"].dtype == pd.Int64Dtype()
