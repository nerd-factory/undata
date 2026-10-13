"""Countries, regions and UN groups, by the names people actually use.

undata's list of countries is the UN's own: the M49 standard of the UN Statistics
Division, shipped with the package in ``m49.csv``. It gives every country and area its
official UN name, its region and sub-region, and whether it is a least developed
country (LDC), a landlocked developing country (LLDC) or a small island developing
State (SIDS). ``scripts/update_m49.py`` refreshes it, and a nightly test checks it
against the UN's current table.

Anywhere undata asks for places you can write a country's UN name, a common short
name, its ISO code or its M49 code (``"Viet Nam"``, ``"Vietnam"``, ``"VNM"``, ``"704"``),
a region (``"Africa"``, ``"Southern Asia"``, ``"Western Africa"``), or a group
(``"LDCs"``, ``"LLDCs"``, ``"SIDS"``). Regions and groups stand for the countries in
them; :func:`undata.totals` asks for the region's own published figure instead.

Places outside M49, which the platform also holds, are not part of any list, region
or group. They can still be asked for by their platform code, such as ``country/XKS``,
and are labelled with the platform's own name.

undata never guesses. A name it does not recognise raises
:class:`~undata.PlaceNotFoundError` with suggestions, instead of quietly becoming some
other country.
"""

from __future__ import annotations

import csv
import difflib
import re
import unicodedata
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from functools import cache
from importlib import resources
from typing import Final, Literal

import pandas as pd

from .errors import AmbiguousPlaceError, PlaceNotFoundError

__all__ = ["M49_RETRIEVED", "M49_SOURCE", "Country", "Place", "countries", "regions", "resolve"]

M49_SOURCE: Final = "https://unstats.un.org/unsd/methodology/m49/overview/"
M49_RETRIEVED: Final = "2026-10-13"

#: The platform's id for the figure an agency published for a region or group, by M49
#: code or group key. Used by :func:`undata.totals`; others have no published figure.
PLATFORM_IDS: Final[Mapping[str, str]] = {
    "001": "Earth",
    "002": "africa",
    "142": "asia",
    "150": "europe",
    "009": "oceania",
    "015": "NorthernAfrica",
    "202": "SubSaharanAfrica",
    "014": "EasternAfrica",
    "017": "MiddleAfrica",
    "018": "SouthernAfrica",
    "011": "WesternAfrica",
    "419": "LatinAmericaAndCaribbean",
    "029": "Caribbean",
    "013": "CentralAmerica",
    "005": "southamerica",
    "143": "CentralAsia",
    "030": "EasternAsia",
    "035": "SouthEasternAsia",
    "034": "SouthernAsia",
    "145": "WesternAsia",
    "151": "EasternEurope",
    "154": "NorthernEurope",
    "039": "SouthernEurope",
    "155": "WesternEurope",
    "830": "ChannelIslands",
    "053": "AustraliaAndNewZealand",
    "054": "Melanesia",
    "057": "Micronesia",
    "061": "Polynesia",
    "LDC": "undata-geo/G00404000",
    "LLDC": "undata-geo/G00403000",
    "SIDS": "undata-geo/G00405000",
}

#: The UN groups M49 marks, with their names.
GROUPS: Final[Mapping[str, str]] = {
    "LDC": "Least developed countries (LDCs)",
    "LLDC": "Landlocked developing countries (LLDCs)",
    "SIDS": "Small island developing States (SIDS)",
    "DEVELOPED": "Developed countries",
    "DEVELOPING": "Developing countries",
}

_FLAGS: Final[Mapping[str, Callable[[Country], bool]]] = {
    "LDC": lambda c: c.ldc,
    "LLDC": lambda c: c.lldc,
    "SIDS": lambda c: c.sids,
    "DEVELOPED": lambda c: c.developed,
    "DEVELOPING": lambda c: not c.developed,
}

#: Other names people use. Keys are normalised; values are ISO3 codes, M49 codes or
#: group keys.
ALIASES: Final[Mapping[str, str]] = {
    "us": "USA",
    "usa": "USA",
    "united states": "USA",
    "uk": "GBR",
    "united kingdom": "GBR",
    "britain": "GBR",
    "great britain": "GBR",
    "drc": "COD",
    "dr congo": "COD",
    "congo drc": "COD",
    "congo kinshasa": "COD",
    "congo republic": "COG",
    "congo brazzaville": "COG",
    "republic of the congo": "COG",
    "ivory coast": "CIV",
    "burma": "MMR",
    "swaziland": "SWZ",
    "macedonia": "MKD",
    "macedonia fyrom": "MKD",
    "palestine": "PSE",
    "palestinian territories": "PSE",
    "vatican": "VAT",
    "vatican city": "VAT",
    "turkey": "TUR",
    "turkiye": "TUR",
    "vietnam": "VNM",
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
    "south korea": "KOR",
    "north korea": "PRK",
    "czech republic": "CZE",
    "cape verde": "CPV",
    "east timor": "TLS",
    "hong kong": "HKG",
    "macau": "MAC",
    "macao": "MAC",
    "federated states of micronesia": "FSM",
    "saint martin": "MAF",
    "sao tome": "STP",
    "st lucia": "LCA",
    "st kitts and nevis": "KNA",
    "st vincent and the grenadines": "VCT",
    "ldc": "LDC",
    "ldcs": "LDC",
    "least developed countries": "LDC",
    "lldc": "LLDC",
    "lldcs": "LLDC",
    "landlocked developing countries": "LLDC",
    "sids": "SIDS",
    "small island developing states": "SIDS",
    "developed": "DEVELOPED",
    "developing": "DEVELOPING",
    "earth": "001",
    "global": "001",
    "all countries": "001",
}


@dataclass(frozen=True, slots=True)
class Country:
    """One row of the UN M49 standard."""

    iso3: str
    m49: str
    name: str
    region: str
    sub_region: str
    intermediate_region: str
    ldc: bool
    lldc: bool
    sids: bool
    developed: bool


@dataclass(frozen=True, slots=True)
class Place:
    """A country, a region, a UN group, or an area outside M49.

    Attributes:
        id: The platform's identifier: ``country/BGD`` for a country, or the id of
            the figure published for a region (``m49/...`` when none is published).
        name: The UN name.
        kind: ``"country"``, ``"region"``, ``"group"``, or ``"area"`` for a place
            outside M49 asked for by its platform code.
        members: For a region or group, the ISO3 codes of its countries.
    """

    id: str
    name: str
    kind: Literal["country", "region", "group", "area"]
    members: tuple[str, ...] = ()

    @property
    def iso3(self) -> str | None:
        """The three-letter ISO code of a country, or ``None`` for a region or group."""
        if self.kind in ("country", "area") and self.id.startswith("country/"):
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


@cache
def _rows() -> tuple[dict[str, str], ...]:
    text = resources.files("undata").joinpath("m49.csv").read_text(encoding="utf-8")
    return tuple(csv.DictReader(text.splitlines()))


@cache
def m49() -> tuple[Country, ...]:
    """The UN M49 list shipped with undata: every country and area with an ISO code."""
    return tuple(
        Country(
            iso3=row["iso3"],
            m49=row["m49"],
            name=row["name"],
            region=row["region"],
            sub_region=row["sub_region"],
            intermediate_region=row["intermediate_region"],
            ldc=row["ldc"] == "x",
            lldc=row["lldc"] == "x",
            sids=row["sids"] == "x",
            developed=row["development"] == "Developed",
        )
        for row in _rows()
    )


def _area(code: str, name: str, kind: Literal["region", "group"], members: Iterable[str]) -> Place:
    return Place(PLATFORM_IDS.get(code, f"m49/{code}"), name, kind, tuple(members))


@cache
def _areas() -> tuple[tuple[str, Place], ...]:
    """Every region and group, keyed by M49 code or group key, world first."""
    found: list[tuple[str, Place]] = [
        ("001", _area("001", "World", "region", (c.iso3 for c in m49())))
    ]
    levels = [
        ("region_code", "region"),
        ("sub_region_code", "sub_region"),
        ("intermediate_region_code", "intermediate_region"),
    ]
    for code_field, name_field in levels:
        seen: dict[str, tuple[str, list[str]]] = {}
        for row in _rows():
            code = row[code_field]
            if code:
                seen.setdefault(code, (row[name_field], []))[1].append(row["iso3"])
        found += [(code, _area(code, name, "region", iso)) for code, (name, iso) in seen.items()]
    for key, test in _FLAGS.items():
        members = (c.iso3 for c in m49() if test(c))
        found.append((key, _area(key, GROUPS[key], "group", members)))
    return tuple(found)


@cache
def _countries() -> dict[str, Place]:
    """Every M49 country and area, by ISO3 code."""
    return {c.iso3: Place(f"country/{c.iso3}", c.name, "country") for c in m49()}


@cache
def _index() -> dict[str, Place]:
    """Every accepted spelling, normalised, mapped to its place."""
    index: dict[str, Place] = {}
    by_iso = _countries()
    for country in m49():
        place = by_iso[country.iso3]
        for key in (country.name, country.iso3, country.m49, str(int(country.m49)), place.id):
            index[_normalise(key)] = place
    keyed = dict(_areas())
    for code, area in keyed.items():
        for key in (area.name, code, area.id):
            index.setdefault(_normalise(key), area)
    for alias, target in ALIASES.items():
        index[alias] = by_iso[target] if target in by_iso else keyed[target]
    return index


def _outside_m49(code: str) -> Place:
    """A platform place outside M49, asked for by its code, under the platform's name."""
    from .indicators import names  # noqa: PLC0415 — places must not import indicators at load

    found = names([code]).get(code)
    if not found:
        raise PlaceNotFoundError(code)
    return Place(code, found, "area")


def resolve(name: str) -> Place:
    """Return the country, region or group a name refers to.

    Args:
        name: A UN name or common name, an ISO3 or M49 code, a region or group name,
            or a platform code such as ``country/XKS`` for a place outside M49.

    Raises:
        PlaceNotFoundError: The name matches nothing. The error lists close matches.
        AmbiguousPlaceError: The name is part of several names, such as "Korea".

    Example:
        >>> import undata as un
        >>> un.places.resolve("Vietnam").name
        'Viet Nam'
        >>> un.places.resolve("LDCs").kind
        'group'
    """
    key = _normalise(name)
    index = _index()
    if key in index:
        return index[key]
    if "/" in name.strip():
        return _outside_m49(name.strip())

    names = sorted({place.name for place in index.values()})
    partial = [n for n in names if key and re.search(rf"\b{re.escape(key)}\b", _normalise(n))]
    if len(partial) > 1:
        raise AmbiguousPlaceError(name, partial)
    close = difflib.get_close_matches(name, names, n=3, cutoff=0.6)
    raise PlaceNotFoundError(name, partial or close)


def expand(places: str | Iterable[str]) -> list[Place]:
    """Resolve names to countries, expanding each region or group into its countries.

    Order is kept and duplicates are dropped, so ``["Nepal", "Southern Asia"]``
    lists Nepal once.
    """
    names = [places] if isinstance(places, str) else list(places)
    if not names:
        raise ValueError("No countries were given. Pass a name, a list of names, or a region.")
    by_iso = _countries()
    seen: dict[str, Place] = {}
    for name in names:
        place = resolve(name)
        grouped = place.kind in ("region", "group")
        inside = [by_iso[i] for i in place.members] if grouped else [place]
        for country in inside:
            seen.setdefault(country.id, country)
    return list(seen.values())


def countries(region: str | None = None) -> pd.DataFrame:
    """List countries and areas, all of them or those in one region or group.

    The list is the UN's M49 standard, with official UN names.

    Args:
        region: A region or group such as ``"Western Africa"``, ``"Asia"`` or
            ``"SIDS"``. Leave it out for every country and area.

    Returns:
        A table with ``country``, ``iso3``, ``m49``, ``region``, ``sub_region``, and
        ``ldc``, ``lldc`` and ``sids`` as true or false. Sorted by name.

    Example:
        >>> import undata as un
        >>> len(un.countries("LDCs")) > 40
        True
    """
    rows = m49()
    if region is not None:
        place = resolve(region)
        if place.kind not in ("region", "group"):
            raise ValueError(f"{place.name} is a country, not a region. See un.regions().")
        wanted = set(place.members)
        rows = tuple(c for c in rows if c.iso3 in wanted)
    frame = pd.DataFrame(
        [
            {
                "country": c.name,
                "iso3": c.iso3,
                "m49": c.m49,
                "region": c.region,
                "sub_region": c.intermediate_region or c.sub_region,
                "ldc": c.ldc,
                "lldc": c.lldc,
                "sids": c.sids,
            }
            for c in rows
        ],
        columns=["country", "iso3", "m49", "region", "sub_region", "ldc", "lldc", "sids"],
    )
    return frame.sort_values("country", key=lambda s: s.map(_normalise), ignore_index=True)


def regions() -> pd.DataFrame:
    """List every region and UN group you can use wherever undata asks for countries.

    Returns:
        A table with ``region``, ``kind`` (region or group), ``code`` (the M49 code
        or group key), ``countries`` (how many), and ``published_total`` (whether the
        platform holds a figure published for the region itself, for
        :func:`undata.totals`).

    Example:
        >>> import undata as un
        >>> "Southern Asia" in set(un.regions()["region"])
        True
    """
    return pd.DataFrame(
        [
            {
                "region": place.name,
                "kind": place.kind,
                "code": code,
                "countries": len(place.members),
                "published_total": not place.id.startswith("m49/"),
            }
            for code, place in _areas()
        ],
        columns=["region", "kind", "code", "countries", "published_total"],
    )
