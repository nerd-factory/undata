from __future__ import annotations

import pytest

import undata as un
from undata.places import Place, expand, resolve

from .fake_api import FakeAPI


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("Bangladesh", "country/BGD"),
        ("bangladesh", "country/BGD"),
        ("  BANGLADESH ", "country/BGD"),
        ("BGD", "country/BGD"),
        ("bgd", "country/BGD"),
        ("country/BGD", "country/BGD"),
        ("Viet Nam", "country/VNM"),  # UN name
        ("Vietnam", "country/VNM"),  # platform name
        ("Türkiye", "country/TUR"),
        ("Turkiye", "country/TUR"),
        ("Turkey", "country/TUR"),
        ("Cote d'Ivoire", "country/CIV"),
        ("C\u00f4te d\u2019Ivoire", "country/CIV"),  # curly apostrophe
        ("ivory coast", "country/CIV"),
        ("UK", "country/GBR"),
        ("the United Kingdom", "country/GBR"),
        ("DRC", "country/COD"),
        ("Congo", "country/COG"),  # the UN short name of the Republic of the Congo
        ("Congo [DRC]", "country/COD"),
        ("Southern Asia", "SouthernAsia"),
        ("southernasia", "SouthernAsia"),
        ("World", "Earth"),
        ("all countries", "Earth"),
    ],
)
def test_resolve_accepts_the_names_people_use(fake: FakeAPI, name: str, expected: str) -> None:
    assert resolve(name).id == expected


def test_countries_carry_their_un_short_name(fake: FakeAPI) -> None:
    assert resolve("Vietnam") == Place("country/VNM", "Viet Nam", "country")
    assert resolve("Turkey").name == "Türkiye"
    assert resolve("Congo [DRC]").name == "Democratic Republic of the Congo"
    assert resolve("Bangladesh").name == "Bangladesh"  # unchanged where they agree


def test_an_unknown_place_raises_with_suggestions_and_is_never_substituted(fake: FakeAPI) -> None:
    with pytest.raises(un.PlaceNotFoundError, match="'Bangladsh' is not a country") as caught:
        resolve("Bangladsh")

    assert caught.value.suggestions == ["Bangladesh"]
    assert "un.countries()" in str(caught.value)


def test_a_partial_name_with_one_match_is_suggested_not_accepted(fake: FakeAPI) -> None:
    with pytest.raises(un.PlaceNotFoundError) as caught:
        resolve("New Guinea")

    assert caught.value.suggestions == ["Papua New Guinea"]
    assert not isinstance(caught.value, un.AmbiguousPlaceError)


def test_a_name_inside_several_countries_is_ambiguous(fake: FakeAPI) -> None:
    with pytest.raises(un.AmbiguousPlaceError, match="could mean more than one") as caught:
        resolve("Republic")

    assert caught.value.suggestions == ["Democratic Republic of the Congo", "Republic of Korea"]
    assert isinstance(caught.value, un.PlaceNotFoundError)  # one except clause catches both


def test_nothing_close_gives_no_suggestions(fake: FakeAPI) -> None:
    with pytest.raises(un.PlaceNotFoundError) as caught:
        resolve("Atlantis")

    assert caught.value.suggestions == []
    assert "Did you mean" not in str(caught.value)


def test_expand_turns_regions_into_countries_keeping_order_without_duplicates(
    fake: FakeAPI,
) -> None:
    places = expand(["Nepal", "Southern Asia", "Norway"])

    assert [p.iso3 for p in places] == ["NPL", "BGD", "NOR"]


def test_expand_world_is_every_country(fake: FakeAPI) -> None:
    assert len(expand("World")) == 11


def test_expand_needs_at_least_one_place(fake: FakeAPI) -> None:
    with pytest.raises(ValueError, match="No countries were given"):
        expand([])


def test_the_country_list_is_fetched_once_per_session(fake: FakeAPI) -> None:
    resolve("Nepal")
    resolve("Norway")
    un.countries()

    assert fake.calls["node"] == 1


def test_countries_lists_every_country_sorted_by_name(fake: FakeAPI) -> None:
    table = un.countries()

    assert list(table.columns) == ["country", "iso3", "id"]
    assert list(table["country"].iloc[:4]) == [
        "Bangladesh",
        "Congo",
        "Côte d'Ivoire",  # sorted ignoring the accent
        "Democratic Republic of the Congo",
    ]
    assert len(table) == 11


def test_countries_in_a_region(fake: FakeAPI) -> None:
    assert list(un.countries("Southern Asia")["iso3"]) == ["BGD", "NPL"]


def test_countries_rejects_a_country_as_a_region(fake: FakeAPI) -> None:
    with pytest.raises(ValueError, match="Nepal is a country, not a region"):
        un.countries("Nepal")


def test_regions_lists_world_continents_and_un_subregions() -> None:
    table = un.regions()

    assert list(table.columns) == ["region", "id"]
    assert {"World", "Africa", "Southern Asia", "Sub-Saharan Africa"} <= set(table["region"])


def test_place_helpers() -> None:
    region = Place("SouthernAsia", "Southern Asia", "region")

    assert region.iso3 is None
    assert str(region) == "Southern Asia"
    assert Place("country/NPL", "Nepal", "country").iso3 == "NPL"


def test_latin_america_alone_is_not_a_region_but_is_suggested(fake: FakeAPI) -> None:
    with pytest.raises(un.PlaceNotFoundError) as caught:
        resolve("Latin America")

    assert caught.value.suggestions == ["Latin America and the Caribbean"]
