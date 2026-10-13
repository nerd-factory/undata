from __future__ import annotations

import pytest

import undata as un
from undata.places import Place, expand, m49, resolve

from .fake_api import FakeAPI


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("Bangladesh", "country/BGD"),
        ("bangladesh", "country/BGD"),
        ("  BANGLADESH ", "country/BGD"),
        ("BGD", "country/BGD"),
        ("bgd", "country/BGD"),
        ("050", "country/BGD"),  # M49 code
        ("50", "country/BGD"),
        ("country/BGD", "country/BGD"),
        ("Viet Nam", "country/VNM"),  # UN name
        ("Vietnam", "country/VNM"),  # common name
        ("Türkiye", "country/TUR"),
        ("Turkiye", "country/TUR"),
        ("Turkey", "country/TUR"),
        ("Cote d'Ivoire", "country/CIV"),
        ("C\u00f4te d\u2019Ivoire", "country/CIV"),  # the UN spelling, curly apostrophe
        ("ivory coast", "country/CIV"),
        ("UK", "country/GBR"),
        ("the United Kingdom", "country/GBR"),
        ("DRC", "country/COD"),
        ("Congo", "country/COG"),  # the UN short name of the Republic of the Congo
        ("Congo [DRC]", "country/COD"),
        ("Southern Asia", "SouthernAsia"),
        ("southernasia", "SouthernAsia"),
        ("034", "SouthernAsia"),
        ("World", "Earth"),
        ("all countries", "Earth"),
        ("LDCs", "undata-geo/G00404000"),
        ("Least developed countries", "undata-geo/G00404000"),
        ("SIDS", "undata-geo/G00405000"),
        ("LLDCs", "undata-geo/G00403000"),
    ],
)
def test_resolve_accepts_the_names_people_use(name: str, expected: str) -> None:
    assert resolve(name).id == expected


def test_countries_carry_their_un_name() -> None:
    assert resolve("Vietnam") == Place("country/VNM", "Viet Nam", "country")
    assert resolve("Turkey").name == "Türkiye"
    assert resolve("Congo [DRC]").name == "Democratic Republic of the Congo"
    assert resolve("Bangladesh").name == "Bangladesh"


def test_the_list_is_the_un_m49_standard() -> None:
    countries = m49()

    assert len(countries) == 248
    assert {c.iso3 for c in countries} >= {"BGD", "ESH", "PSE", "TUR"}
    assert not {"TWN", "XKS", "YUG", "ANT"} & {c.iso3 for c in countries}
    assert sum(c.ldc for c in countries) == 44
    assert sum(c.sids for c in countries) == 53


def test_an_unknown_place_raises_with_suggestions_and_is_never_substituted() -> None:
    with pytest.raises(un.PlaceNotFoundError, match="'Bangladsh' is not a country") as caught:
        resolve("Bangladsh")

    assert caught.value.suggestions == ["Bangladesh"]
    assert "un.countries()" in str(caught.value)


def test_a_partial_name_with_one_match_is_suggested_not_accepted() -> None:
    with pytest.raises(un.PlaceNotFoundError) as caught:
        resolve("New Guinea")

    assert caught.value.suggestions == ["Papua New Guinea"]
    assert not isinstance(caught.value, un.AmbiguousPlaceError)


def test_a_name_inside_several_countries_is_ambiguous() -> None:
    with pytest.raises(un.AmbiguousPlaceError, match="could mean more than one") as caught:
        resolve("Korea")

    assert caught.value.suggestions == [
        "Democratic People's Republic of Korea",
        "Republic of Korea",
    ]
    assert isinstance(caught.value, un.PlaceNotFoundError)  # one except clause catches both


def test_nothing_close_gives_no_suggestions() -> None:
    with pytest.raises(un.PlaceNotFoundError) as caught:
        resolve("Zzyzx")

    assert caught.value.suggestions == []
    assert "Did you mean" not in str(caught.value)


def test_regions_outside_m49_point_to_the_m49_one() -> None:
    with pytest.raises(un.PlaceNotFoundError) as caught:
        resolve("North America")

    assert caught.value.suggestions[0] == "Northern America"


def test_a_place_outside_m49_is_reachable_only_by_its_platform_code(fake: FakeAPI) -> None:
    kosovo = resolve("country/XKS")

    assert kosovo == Place("country/XKS", "Kosovo", "area")
    assert kosovo.iso3 == "XKS"
    with pytest.raises(un.PlaceNotFoundError):
        resolve("Kosovo")
    with pytest.raises(un.PlaceNotFoundError):
        resolve("country/NOPE")


def test_expand_turns_regions_into_countries_keeping_order_without_duplicates() -> None:
    places = expand(["Nepal", "Southern Asia", "Norway"])

    assert [p.iso3 for p in places] == [
        "NPL", "AFG", "BGD", "BTN", "IND", "IRN", "LKA", "MDV", "PAK", "NOR",
    ]  # fmt: skip


def test_expand_world_is_every_country_and_groups_are_their_members() -> None:
    assert len(expand("World")) == 248
    ldcs = {p.iso3 for p in expand("LDCs")}
    assert len(ldcs) == 44
    assert {"BGD", "NPL", "COD"} <= ldcs


def test_expand_needs_at_least_one_place() -> None:
    with pytest.raises(ValueError, match="No countries were given"):
        expand([])


def test_places_need_no_request_to_the_platform(fake: FakeAPI) -> None:
    resolve("Nepal")
    expand(["Africa", "LDCs"])
    un.countries("SIDS")

    assert fake.calls["node"] == 0


def test_countries_lists_every_country_sorted_by_name() -> None:
    table = un.countries()

    assert list(table.columns) == [
        "country", "iso3", "m49", "region", "sub_region", "ldc", "lldc", "sids",
    ]  # fmt: skip
    assert len(table) == 248
    assert list(table["country"].iloc[:3]) == ["Afghanistan", "Åland Islands", "Albania"]
    afghanistan = table.iloc[0]
    assert (afghanistan["region"], afghanistan["ldc"], afghanistan["sids"]) == ("Asia", True, False)


def test_countries_in_a_region_or_group() -> None:
    assert list(un.countries("Southern Asia")["iso3"]) == [
        "AFG", "BGD", "BTN", "IND", "IRN", "MDV", "NPL", "PAK", "LKA",
    ]  # fmt: skip
    assert len(un.countries("SIDS")) == 53


def test_countries_rejects_a_country_as_a_region() -> None:
    with pytest.raises(ValueError, match="Nepal is a country, not a region"):
        un.countries("Nepal")


def test_regions_lists_world_regions_subregions_and_groups() -> None:
    table = un.regions()

    assert list(table.columns) == ["region", "kind", "code", "countries", "published_total"]
    assert table.iloc[0].to_dict() == {
        "region": "World",
        "kind": "region",
        "code": "001",
        "countries": 248,
        "published_total": True,
    }
    names = set(table["region"])
    assert {
        "Africa",
        "Southern Asia",
        "Western Africa",
        "Small island developing States (SIDS)",
    } <= names
    assert not table.set_index("region").loc["Americas", "published_total"]


def test_latin_america_alone_is_not_a_region_but_is_suggested() -> None:
    with pytest.raises(un.PlaceNotFoundError) as caught:
        resolve("Latin America")

    assert caught.value.suggestions == ["Latin America and the Caribbean"]


def test_place_helpers() -> None:
    region = resolve("Southern Asia")

    assert region.iso3 is None
    assert str(region) == "Southern Asia"
    assert len(region.members) == 9
    assert Place("country/NPL", "Nepal", "country").iso3 == "NPL"
