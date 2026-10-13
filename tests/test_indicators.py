from __future__ import annotations

import pytest

import undata as un
from undata.indicators import check, names, source_label

from .fake_api import MMR, FakeAPI


def test_search_shows_un_collections_only_by_default(fake: FakeAPI) -> None:
    table = un.search("maternal mortality")

    assert list(table.columns) == ["indicator", "name", "source"]
    assert all(table["indicator"].str.startswith("undata/"))


def test_search_ranks_names_with_all_the_words_first(fake: FakeAPI) -> None:
    table = un.search("maternal mortality")

    assert table["indicator"].iloc[0] == MMR
    assert table["source"].iloc[0] == "Global SDG Indicators Database"


def test_search_can_include_other_sources_and_labels_them(fake: FakeAPI) -> None:
    table = un.search("maternal mortality", all_sources=True)

    copies = table[~table["indicator"].str.startswith("undata/")]
    assert set(copies["indicator"]) == {"sdg/SH_STA_MORT.SEX--F", "Count_Person"}
    assert set(copies["source"]) == {"Data Commons (not a UN collection)"}


def test_search_respects_the_limit_and_handles_no_results(fake: FakeAPI) -> None:
    assert len(un.search("maternal mortality", limit=2)) == 2
    assert un.search("nothing like this").empty


def test_names_are_cached_and_unknown_ids_are_absent(fake: FakeAPI) -> None:
    assert names([MMR, "undata/sdg/NOPE"]) == {MMR: "Maternal mortality ratio [Sex=Female]"}
    assert names([MMR]) == {MMR: "Maternal mortality ratio [Sex=Female]"}
    assert fake.calls["node"] == 1


def test_source_label_flags_copies_imported_by_data_commons(fake: FakeAPI) -> None:
    assert source_label("undata/p/SDG") == "SDG Global Database"
    assert source_label("dc/base/UN_SDG") == "UN_SDG (Data Commons copy)"
    assert source_label("undata/p/UNKNOWN") == "UNKNOWN"


def test_check_returns_names_in_order(fake: FakeAPI) -> None:
    assert check([MMR]) == {MMR: "Maternal mortality ratio [Sex=Female]"}


def test_a_phrase_instead_of_an_id_explains_and_suggests(fake: FakeAPI) -> None:
    with pytest.raises(un.IndicatorNotFoundError, match="looks like a description") as caught:
        check("maternal mortality")

    assert caught.value.suggestions[0] == MMR
    assert "un.search('maternal mortality')" in str(caught.value)


def test_an_unknown_id_is_reported(fake: FakeAPI) -> None:
    with pytest.raises(un.IndicatorNotFoundError, match="No indicator has the id"):
        check("undata/sdg/NOPE")


def test_check_needs_an_indicator(fake: FakeAPI) -> None:
    with pytest.raises(ValueError, match="No indicators were given"):
        check([])
    with pytest.raises(un.IndicatorNotFoundError):
        check("   ")


def test_suggestions_never_hide_the_real_error(
    fake: FakeAPI, monkeypatch: pytest.MonkeyPatch
) -> None:
    def broken(*_: object) -> None:
        raise un.ConnectionFailedError("down", url="x")

    monkeypatch.setattr("undata._endpoints.stat_var_search", broken)

    with pytest.raises(un.IndicatorNotFoundError) as caught:
        check("maternal mortality")

    assert caught.value.suggestions == []


def test_about_describes_the_main_source(fake: FakeAPI) -> None:
    info = un.about(MMR)

    assert info == un.IndicatorInfo(
        indicator=MMR,
        name="Maternal mortality ratio [Sex=Female]",
        source="SDG Global Database",
        unit="Count per 100,000 live births",
        first_year="2000",
        last_year="2023",
        places=233,
        observations=5592,
    )
    text = repr(info)
    assert text.splitlines()[0] == "Maternal mortality ratio [Sex=Female]"
    assert "2000 to 2023" in text
    assert "5,592" in text


def test_about_an_indicator_with_no_data(fake: FakeAPI) -> None:
    info = un.about("undata/sdg/EG_ACS_ELEC")

    assert info.observations == 0
    assert "not stated" in repr(info)
