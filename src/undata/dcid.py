"""The identifier grammar of the UN System Data Commons.

Every statistical variable in the graph has a structured identifier, a *dcid*.
Learn the grammar and you can read the address of a slice you have never seen::

    undata / sdg / VC_DTH_TOTN . AGE--Y0T17 __ SEX--F
    ──┬───   ─┬─   ─────┬─────   ────┬────      ──┬──
      │       │         │            │            └── second dimension filter
      │       │         │            └─────────────── first dimension filter
      │       │         └──────────────────────────── the indicator's series code
      │       └────────────────────────────────────── contributing collection
      └────────────────────────────────────────────── namespace

``.`` opens the dimension list, ``--`` binds a dimension to a value, and ``__``
separates dimensions. An identifier with no ``.`` is the undisaggregated series.

Two warnings the grammar does not tell you about:

* The bare code is not always published. Maternal mortality exists only as
  ``undata/sdg/SH_STA_MORT.SEX--F``; the unsuffixed identifier returns nothing.
  Confirm identifiers against the graph rather than building them by analogy.
* Age and sex slices leave out the "unknown" category, which is carried in its own
  slice (``AGE--_U``). Summing the named slices will not reproduce the total.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Final

__all__ = [
    "AGENCY_LABELS",
    "Dimension",
    "ParsedDcid",
    "build_dcid",
    "child_countries_of",
    "describe_dcid",
    "parse_dcid",
]

_DIMENSION_SEPARATOR: Final = "__"
_DIMENSION_BINDING: Final = "--"

#: Display names for the collection segment of a dcid. Keyed by the identifier the
#: graph uses, which is not always the agency's acronym: ``sdg`` is the Global SDG
#: Indicators Database, contributed by UNSD rather than by an agency of that name.
AGENCY_LABELS: Final[Mapping[str, str]] = {
    "sdg": "Global SDG Indicators Database",
    "sdgf": "SDG framework",
    "eclac": "ECLAC",
    "ilo": "ILO",
    "iomdtm": "IOM DTM",
    "itu": "ITU",
    "ohchr": "OHCHR",
    "unaids": "UNAIDS",
    "undphdro": "UNDP HDRO",
    "undrr": "UNDRR",
    "unesco": "UNESCO",
    "unfpa": "UNFPA",
    "unhcr": "UNHCR",
    "unicef": "UNICEF",
    "unido": "UNIDO",
    "unodc": "UNODC",
    "who": "WHO",
    "topic": "Topic",
}


@dataclass(frozen=True, slots=True)
class Dimension:
    """One dimension filter in a dcid, such as ``SEX--F``."""

    name: str
    value: str

    def __str__(self) -> str:
        return f"{self.name}{_DIMENSION_BINDING}{self.value}"


@dataclass(frozen=True, slots=True)
class ParsedDcid:
    """A variable dcid split into its parts.

    Attributes:
        namespace: ``undata`` for variables native to this deployment.
        agency: The contributing collection, e.g. ``sdg``, ``unodc``, ``who``.
        code: The indicator code without any dimension filters.
        dimensions: Dimension filters, in the order they appear.
    """

    namespace: str
    agency: str
    code: str
    dimensions: tuple[Dimension, ...] = ()

    @property
    def base(self) -> str:
        """The undisaggregated identifier, with every dimension removed."""
        return f"{self.namespace}/{self.agency}/{self.code}"

    @property
    def is_total(self) -> bool:
        """True when the identifier carries no dimension filters."""
        return not self.dimensions

    @property
    def agency_label(self) -> str:
        """A readable name for the contributing collection."""
        return AGENCY_LABELS.get(self.agency, self.agency.upper())


def parse_dcid(dcid: str) -> ParsedDcid | None:
    """Parse a variable dcid into its parts.

    Returns ``None`` rather than raising for anything that is not a path of three or
    more segments, such as ``Count_Person`` or ``country/BGD``, so callers can treat
    unfamiliar identifiers as opaque on a graph that is still growing.

    Example:
        >>> parsed = parse_dcid("undata/sdg/VC_DTH_TOTN.AGE--Y0T17__SEX--F")
        >>> parsed.code, [str(d) for d in parsed.dimensions]
        ('VC_DTH_TOTN', ['AGE--Y0T17', 'SEX--F'])
        >>> parsed.base
        'undata/sdg/VC_DTH_TOTN'
        >>> parse_dcid("Count_Person") is None
        True
    """
    segments = dcid.strip().split("/")
    if len(segments) < 3 or not all(segments[:2]):  # noqa: PLR2004 — namespace/agency/code
        return None

    namespace, agency = segments[0], segments[1]
    # Topic dcids nest one level deeper (undata/topic/sdg/...); keep the tail intact.
    tail = "/".join(segments[2:])
    code, _, dimension_part = tail.partition(".")
    if not code:
        return None

    return ParsedDcid(namespace, agency, code, _parse_dimensions(dimension_part))


def _parse_dimensions(part: str) -> tuple[Dimension, ...]:
    dimensions: list[Dimension] = []
    for chunk in part.split(_DIMENSION_SEPARATOR) if part else ():
        name, binding, value = chunk.partition(_DIMENSION_BINDING)
        if name and binding:
            dimensions.append(Dimension(name, value))
    return tuple(dimensions)


def build_dcid(base: str, dimensions: Mapping[str, str] | None = None) -> str:
    """Build a variable dcid from its base and dimension filters.

    Dimensions are sorted by name, as they are in the graph's own identifiers, so
    the same slice always produces the same identifier whatever order you pass them in.

    Example:
        >>> build_dcid("undata/sdg/VC_DTH_TOTN", {"SEX": "F", "AGE": "Y0T17"})
        'undata/sdg/VC_DTH_TOTN.AGE--Y0T17__SEX--F'
    """
    if not dimensions:
        return base
    encoded = _DIMENSION_SEPARATOR.join(
        str(Dimension(name, value)) for name, value in sorted(dimensions.items())
    )
    return f"{base}.{encoded}"


def describe_dcid(dcid: str) -> str:
    """Return a short human-readable gloss of a dcid.

    Example:
        >>> describe_dcid("undata/sdg/SH_STA_MORT.SEX--F")
        'Global SDG Indicators Database · SH_STA_MORT [SEX=F]'
    """
    parsed = parse_dcid(dcid)
    if parsed is None:
        return dcid
    if parsed.is_total:
        return f"{parsed.agency_label} · {parsed.code} (total)"
    slice_ = ", ".join(f"{d.name}={d.value}" for d in parsed.dimensions)
    return f"{parsed.agency_label} · {parsed.code} [{slice_}]"


def child_countries_of(place: str) -> str:
    """Return the relation expression for every country inside ``place``.

    ``<-containedInPlace+`` walks containment inward and recursively, so one request
    covers a whole continent; ``{typeOf:Country}`` keeps other place types out.

    Example:
        >>> child_countries_of("africa")
        'africa<-containedInPlace+{typeOf:Country}'
    """
    return f"{place}<-containedInPlace+{{typeOf:Country}}"
