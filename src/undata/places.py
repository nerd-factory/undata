"""Countries and regions, by the names people actually use.

Anywhere undata asks for places you can write a country's name, its UN name, a
common short name, or its three-letter ISO code — ``"Viet Nam"``, ``"Vietnam"``
and ``"VNM"`` all work — or a region such as ``"Southern Asia"`` or ``"Africa"``,
which stands for every country in it. The UN development groupings work the same
way: ``"LDCs"``, ``"LLDCs"`` and ``"SIDS"``.

Tables use the UN's own short names (M49), so ``Türkiye`` and ``Viet Nam`` rather
than the platform's ``Turkey`` and ``Vietnam``, and can go straight into a UN report.

undata never guesses. A name it does not recognise raises
:class:`~undata.PlaceNotFoundError` with suggestions, instead of quietly becoming
some other country.
"""

from __future__ import annotations

import difflib
import re
import unicodedata
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Final, Literal

import pandas as pd

from . import _endpoints as api
from . import _session
from .errors import AmbiguousPlaceError, PlaceNotFoundError

__all__ = ["Place", "countries", "regions", "resolve"]

WORLD: Final = "Earth"
_COUNTRIES_IN: Final = "<-containedInPlace+{typeOf:Country}"

#: Regions, by graph id. Continents, the UN M49 sub-regions, and the world. The
#: platform's "Latin America" region holds no countries, so it is left out;
#: "Latin America and the Caribbean" is the one to use.
REGIONS: Final[Mapping[str, str]] = {
    "Earth": "World",
    "africa": "Africa",
    "asia": "Asia",
    "europe": "Europe",
    "northamerica": "North America",
    "southamerica": "South America",
    "oceania": "Oceania",
    "AustraliaAndNewZealand": "Australia and New Zealand",
    "Caribbean": "Caribbean",
    "CentralAmerica": "Central America",
    "CentralAsia": "Central Asia",
    "ChannelIslands": "Channel Islands",
    "EasternAfrica": "Eastern Africa",
    "EasternAsia": "Eastern Asia",
    "EasternEurope": "Eastern Europe",
    "LatinAmericaAndCaribbean": "Latin America and the Caribbean",
    "Melanesia": "Melanesia",
    "Micronesia": "Micronesia",
    "MiddleAfrica": "Middle Africa",
    "NorthernAfrica": "Northern Africa",
    "NorthernEurope": "Northern Europe",
    "Polynesia": "Polynesia",
    "SouthEasternAsia": "South-Eastern Asia",
    "SouthernAfrica": "Southern Africa",
    "SouthernAsia": "Southern Asia",
    "SouthernEurope": "Southern Europe",
    "SubSaharanAfrica": "Sub-Saharan Africa",
    "WesternAfrica": "Western Africa",
    "WesternAsia": "Western Asia",
    "WesternEurope": "Western Europe",
    # UN development groupings. The platform also holds OECD and developed/developing
    # groupings, but their member lists are empty or wrong, so they are left out.
    "undata-geo/G00404000": "Least developed countries (LDCs)",
    "undata-geo/G00403000": "Landlocked developing countries (LLDCs)",
    "undata-geo/G00405000": "Small Island Developing States (SIDS)",
}

#: UN M49 short names, where they differ from the platform's names. Keyed by ISO3.
UN_NAMES: Final[Mapping[str, str]] = {
    "BOL": "Bolivia (Plurinational State of)",
    "BRN": "Brunei Darussalam",
    "COD": "Democratic Republic of the Congo",
    "COG": "Congo",
    "CPV": "Cabo Verde",
    "CZE": "Czechia",
    "FLK": "Falkland Islands (Malvinas)",
    "FSM": "Micronesia (Federated States of)",
    "GBR": "United Kingdom of Great Britain and Northern Ireland",
    "HKG": "China, Hong Kong Special Administrative Region",
    "IRN": "Iran (Islamic Republic of)",
    "KOR": "Republic of Korea",
    "LAO": "Lao People's Democratic Republic",
    "MAC": "China, Macao Special Administrative Region",
    "MAF": "Saint Martin (French Part)",
    "MDA": "Republic of Moldova",
    "MKD": "North Macedonia",
    "NLD": "Netherlands (Kingdom of the)",
    "PCN": "Pitcairn",
    "PRK": "Democratic People's Republic of Korea",
    "PSE": "State of Palestine",
    "RUS": "Russian Federation",
    "STP": "Sao Tome and Principe",
    "SXM": "Sint Maarten (Dutch part)",
    "SYR": "Syrian Arab Republic",
    "TLS": "Timor-Leste",
    "TUR": "Türkiye",
    "TZA": "United Republic of Tanzania",
    "UMI": "United States Minor Outlying Islands",
    "USA": "United States of America",
    "VAT": "Holy See",
    "VEN": "Venezuela (Bolivarian Republic of)",
    "VIR": "United States Virgin Islands",
    "VNM": "Viet Nam",
    "WLF": "Wallis and Futuna Islands",
}

#: Other names people use. Keys are normalised; values are ISO3 codes or region ids.
ALIASES: Final[Mapping[str, str]] = {
    "us": "USA",
    "united states": "USA",
    "america": "USA",
    "uk": "GBR",
    "britain": "GBR",
    "great britain": "GBR",
    "england": "GBR",
    "drc": "COD",
    "dr congo": "COD",
    "congo kinshasa": "COD",
    "congo brazzaville": "COG",
    "republic of the congo": "COG",
    "ivory coast": "CIV",
    "burma": "MMR",
    "swaziland": "SWZ",
    "macedonia": "MKD",
    "palestine": "PSE",
    "vatican": "VAT",
    "turkiye": "TUR",
    "moldova": "MDA",
    "tanzania": "TZA",
    "syria": "SYR",
    "laos": "LAO",
    "iran": "IRN",
    "russia": "RUS",
    "bolivia": "BOL",
    "venezuela": "VEN",
    "brunei": "BRN",
    "netherlands": "NLD",
    "holland": "NLD",
    "ldc": "undata-geo/G00404000",
    "ldcs": "undata-geo/G00404000",
    "least developed countries": "undata-geo/G00404000",
    "lldc": "undata-geo/G00403000",
    "lldcs": "undata-geo/G00403000",
    "landlocked developing countries": "undata-geo/G00403000",
    "sids": "undata-geo/G00405000",
    "small island developing states": "undata-geo/G00405000",
    "world": "Earth",
    "global": "Earth",
    "all countries": "Earth",
}


@dataclass(frozen=True, slots=True)
class Place:
    """A country or a region.

    Attributes:
        id: The platform's identifier, e.g. ``country/BGD`` or ``SouthernAsia``.
        name: The UN short name for a country, or the region's name.
        kind: ``"country"`` or ``"region"``.
    """

    id: str
    name: str
    kind: Literal["country", "region"]

    @property
    def iso3(self) -> str | None:
        """The three-letter ISO code of a country, or ``None`` for a region."""
        if self.kind == "country" and self.id.startswith("country/"):
            return self.id.removeprefix("country/")
        return None

    def __str__(self) -> str:
        return self.name


def _normalise(text: str) -> str:
    """Fold case, accents, punctuation and spacing so that spellings compare equal."""
    decomposed = unicodedata.normalize("NFKD", text)
    stripped = "".join(c for c in decomposed if not unicodedata.combining(c))
    folded = stripped.casefold().replace("&", " and ").replace("'", "").replace("\u2019", "")
    words = re.sub(r"[^a-z0-9]+", " ", folded).split()
    if words and words[0] == "the":
        words = words[1:]
    return " ".join(words)


def _platform_names() -> dict[str, str]:
    """The platform's own name for every country it knows, by id. Fetched once."""

    def load() -> dict[str, str]:
        body = api.node(_session.transport(), WORLD, _COUNTRIES_IN)
        nodes = body["data"][WORLD]["arcs"]["containedInPlace+"]["nodes"]
        return {node["dcid"]: node.get("name", "") for node in nodes}

    return _session.cached("platform-names", load)


def _country_table() -> dict[str, Place]:
    """Every country the platform knows, by id, under its UN short name."""

    def build() -> dict[str, Place]:
        table: dict[str, Place] = {}
        for dcid, platform_name in _platform_names().items():
            iso3 = dcid.removeprefix("country/")
            table[dcid] = Place(dcid, UN_NAMES.get(iso3, platform_name or iso3), "country")
        return table

    return _session.cached("countries", build)


def _index() -> dict[str, Place]:
    """Every accepted spelling, normalised, mapped to its place."""

    def build() -> dict[str, Place]:
        table = _country_table()
        index: dict[str, Place] = {}
        for dcid, name in _platform_names().items():
            if name:
                index[_normalise(name)] = table[dcid]
        for place in table.values():
            index[_normalise(place.name)] = place
            index[_normalise(place.id)] = place
            if place.iso3:
                index[place.iso3.casefold()] = place
        for dcid, name in REGIONS.items():
            region = Place(dcid, name, "region")
            index[_normalise(name)] = region
            index[dcid.casefold()] = region
        for alias, target in ALIASES.items():
            if target in REGIONS:
                index[alias] = Place(target, REGIONS[target], "region")
            elif f"country/{target}" in table:
                index[alias] = table[f"country/{target}"]
        return index

    return _session.cached("place-index", build)


def resolve(name: str) -> Place:
    """Return the country or region a name refers to.

    Args:
        name: A country or region name, a three-letter ISO code, or a platform id.

    Raises:
        PlaceNotFoundError: The name matches nothing. The error lists close matches.
        AmbiguousPlaceError: The name is part of several country names, such as "Congo".

    Example:
        >>> import undata as un
        >>> un.places.resolve("Viet Nam")  # doctest: +SKIP
        Place(id='country/VNM', name='Viet Nam', kind='country')
    """
    key = _normalise(name)
    index = _index()
    if key in index:
        return index[key]

    names = sorted({place.name for place in index.values()})
    partial = [n for n in names if key and re.search(rf"\b{re.escape(key)}\b", _normalise(n))]
    if len(partial) > 1:
        raise AmbiguousPlaceError(name, partial)
    close = difflib.get_close_matches(name, names, n=3, cutoff=0.6)
    raise PlaceNotFoundError(name, partial or close)


def _members(region: Place) -> list[Place]:
    """The countries in a region, as the platform's graph records them."""
    if region.id == WORLD:
        return list(_country_table().values())

    def load() -> list[Place]:
        body = api.node(_session.transport(), region.id, _COUNTRIES_IN)
        arcs = body.get("data", {}).get(region.id, {}).get("arcs", {})
        table = _country_table()
        nodes = arcs.get("containedInPlace+", {}).get("nodes", [])
        return [table[n["dcid"]] for n in nodes if n["dcid"] in table]

    return _session.cached(f"members:{region.id}", load)


def expand(places: str | Iterable[str]) -> list[Place]:
    """Resolve names to countries, expanding each region into its countries.

    Order is kept and duplicates are dropped, so ``["Nepal", "Southern Asia"]``
    lists Nepal once.
    """
    names = [places] if isinstance(places, str) else list(places)
    if not names:
        raise ValueError("No countries were given. Pass a name, a list of names, or a region.")
    seen: dict[str, Place] = {}
    for name in names:
        place = resolve(name)
        for country in _members(place) if place.kind == "region" else [place]:
            seen.setdefault(country.id, country)
    return list(seen.values())


def countries(region: str | None = None) -> pd.DataFrame:
    """List countries, optionally only those in one region.

    Args:
        region: A region such as ``"Western Africa"`` or ``"Asia"``. Leave it out
            for every country the platform knows.

    Returns:
        A table with columns ``country``, ``iso3`` and ``id``, sorted by name.

    Example:
        >>> import undata as un
        >>> un.countries("Southern Asia")  # doctest: +SKIP
              country iso3           id
        0  Afghanistan  AFG  country/AFG
        ...
    """
    if region is None:
        members = list(_country_table().values())
    else:
        place = resolve(region)
        if place.kind != "region":
            raise ValueError(f"{place.name} is a country, not a region. See un.regions().")
        members = _members(place)
    frame = pd.DataFrame(
        [{"country": p.name, "iso3": p.iso3, "id": p.id} for p in members],
        columns=["country", "iso3", "id"],
    )
    return frame.sort_values("country", key=lambda s: s.map(_normalise), ignore_index=True)


def regions() -> pd.DataFrame:
    """List the regions you can use wherever undata asks for countries.

    Returns:
        A table with columns ``region`` and ``id``: the world, the continents, and
        the UN M49 sub-regions.

    Example:
        >>> import undata as un
        >>> "Southern Asia" in set(un.regions()["region"])
        True
    """
    return pd.DataFrame(
        [{"region": name, "id": dcid} for dcid, name in REGIONS.items()],
        columns=["region", "id"],
    )
