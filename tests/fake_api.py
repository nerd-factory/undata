"""A small, in-memory stand-in for the platform, shaped like the real responses.

Installed by the ``fake`` fixture in conftest.py. Every response shape here was
copied from a real call; tests/live/ checks the real API still answers that way.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from typing import Any

MMR = "undata/sdg/SH_STA_MORT.SEX--F"
ELEC = "undata/sdg/EG_ACS_ELEC"
RAW = "undata/sdg/RAW_UNIT"
UNIT_ID = "undata/UNIT_MEASURE-RATIO_COUNT_PER_100000_COUNT_LIVEBIRTHS"

COUNTRIES = {
    "country/BGD": "Bangladesh",
    "country/NPL": "Nepal",
    "country/NOR": "Norway",
    "country/COD": "Congo [DRC]",
    "country/COG": "Congo [Republic]",
    "country/VNM": "Vietnam",
    "country/TUR": "Turkey",
    "country/CIV": "Côte d'Ivoire",
    "country/GBR": "United Kingdom",
    "country/KOR": "South Korea",
    "country/PNG": "Papua New Guinea",
}
REGION_MEMBERS = {"SouthernAsia": ["country/BGD", "country/NPL"]}

NAMES = {
    MMR: "Maternal mortality ratio [Sex=Female]",
    ELEC: "Proportion of population with access to electricity",
    RAW: "An indicator whose unit arrives as a graph id",
    "undata/p/SDG": "SDG Global Database",
    "dc/base/UN_SDG": "UN_SDG",
    UNIT_ID: "Count per 100,000 live births",
}

SDG_TREE: dict[str, list[tuple[str, str]]] = {
    "undata/g/sdgf/Root": [
        ("undata/g/sdgf/goal-16", "SDG Goal 16 — Promote peaceful and inclusive societies"),
        ("undata/g/sdgf/goal-3", "SDG Goal 3 — Ensure healthy lives"),
    ],
    "undata/g/sdgf/goal-16": [
        ("undata/g/sdgf/target-16-a", "SDG Target 16.a — Strengthen national institutions"),
        ("undata/g/sdgf/target-16-10", "SDG Target 16.10 — Ensure public access to information"),
        (
            "undata/g/sdgf/target-16-1",
            "SDG Target 16.1 — Significantly reduce all forms of violence",
        ),
    ],
    "undata/g/sdgf/target-16-1": [
        ("undata/g/sdgf/ind-16-1-2", "SDG Indicator 16.1.2 — Conflict-related deaths"),
        ("undata/g/sdgf/ind-16-1-1", "SDG Indicator 16.1.1 — Victims of intentional homicide"),
    ],
    "undata/g/sdgf/ind-16-1-2": [
        ("undata/g/sdg/VC_DTH_TOTR", "Conflict-related deaths per 100,000 population"),
        ("undata/g/sdg/VC_DTH_TOTN", "Number of total conflict-related deaths"),
    ],
    "undata/g/sdg/VC_DTH_TOTR": [("undata/g/sdg/VC_DTH_TOTR.000", "total")],
    "undata/g/sdg/VC_DTH_TOTN": [
        ("undata/g/sdg/VC_DTH_TOTN.000", "total"),
        ("undata/g/sdg/VC_DTH_TOTN.001", "by sex"),
    ],
}
SDG_MEMBERS = {
    "undata/g/sdg/VC_DTH_TOTR.000": [("undata/sdg/VC_DTH_TOTR", "Conflict deaths per 100,000")],
    "undata/g/sdg/VC_DTH_TOTN.000": [("undata/sdg/VC_DTH_TOTN", "Conflict deaths")],
    "undata/g/sdg/VC_DTH_TOTN.001": [
        ("undata/sdg/VC_DTH_TOTN.SEX--F", "Conflict deaths [Female]"),
        ("undata/sdg/VC_DTH_TOTN", "Conflict deaths"),  # listed twice in the graph
    ],
}

SERIES = {
    (MMR, "country/BGD"): [
        (str(y), v)
        for y, v in zip(range(2019, 2024), [160, 151.8, 193.9, 130.5, 115.1], strict=True)
    ],
    (MMR, "country/NPL"): [("2021", 180.0), ("2022", 174.0)],
    (ELEC, "country/BGD"): [("2022", 99.0), ("2024", 99.5)],
    (ELEC, "country/NPL"): [("2018", 90.0)],
    (RAW, "country/BGD"): [("2023", 1.0)],
}
SERIES_FACET = {MMR: "f-sdg", ELEC: "f-copy", RAW: "f-raw-unit"}
FACETS = {
    "f-sdg": {
        "provenanceId": "undata/p/SDG",
        "provenanceUrl": "https://unstats.un.org/sdgs/dataportal",
        "unitDisplayName": "Count per 100,000 live births",
    },
    "f-copy": {
        "provenanceId": "dc/base/UN_SDG",
        "provenanceUrl": "https://unstats.un.org/sdgs/dataportal",
        "unit": "Percent",
    },
    "f-raw-unit": {"provenanceId": "undata/p/SDG", "unit": UNIT_ID},
}

SEARCH_HITS = [
    {"dcid": "sdg/SH_STA_MORT.SEX--F", "name": "Maternal mortality ratio [Female]"},
    {"dcid": "undata/who/MORT.CAUSE--MAT", "name": "Projected death rate [Maternal conditions]"},
    {"dcid": "undata/unicef/MNCH_DEATHS.SEX--F", "name": "Estimated number maternal deaths"},
    {"dcid": MMR, "name": "Maternal mortality ratio [Sex=Female]"},
    {"dcid": "Count_Person", "name": "Population"},
]


class FakeAPI:
    """Replacements for the functions in ``undata._endpoints``, with a call log."""

    def __init__(self) -> None:
        self.calls: Counter[str] = Counter()

    def node(self, _t: object, nodes: str | Sequence[str], prop: str) -> dict[str, Any]:
        self.calls["node"] += 1
        ids = [nodes] if isinstance(nodes, str) else list(nodes)
        data: dict[str, Any] = {}
        for node in ids:
            if prop == "<-containedInPlace+{typeOf:Country}":
                members = list(COUNTRIES) if node == "Earth" else REGION_MEMBERS.get(node, [])
                values = [{"dcid": d, "name": COUNTRIES[d], "types": ["Country"]} for d in members]
                data[node] = {"arcs": {"containedInPlace+": {"nodes": values}}}
            elif prop == "->name" and node in NAMES:
                data[node] = {"arcs": {"name": {"nodes": [{"value": NAMES[node]}]}}}
            elif prop == "<-specializationOf" and node in SDG_TREE:
                values = [{"dcid": d, "name": n} for d, n in SDG_TREE[node]]
                data[node] = {"arcs": {"specializationOf": {"nodes": values}}}
            elif prop == "<-memberOf" and node in SDG_MEMBERS:
                values = [{"dcid": d, "name": n} for d, n in SDG_MEMBERS[node]]
                data[node] = {"arcs": {"memberOf": {"nodes": values}}}
            else:
                data[node] = {}
        return {"data": data}

    def series(
        self, _t: object, variables: Sequence[str], entities: Sequence[str]
    ) -> dict[str, Any]:
        self.calls["series"] += 1
        data: dict[str, Any] = {}
        for variable in variables:
            data[variable] = {}
            for entity in entities:
                points = SERIES.get((variable, entity))
                if points:
                    data[variable][entity] = {
                        "facet": SERIES_FACET[variable],
                        "series": [{"date": d, "value": v} for d, v in points],
                    }
        return {"data": data, "facets": FACETS}

    def stat_var_search(self, _t: object, query: str) -> dict[str, Any]:
        self.calls["search"] += 1
        return {"statVars": SEARCH_HITS if "matern" in query.casefold() else []}

    def variable_info(self, _t: object, dcids: str | Sequence[str]) -> dict[str, Any]:
        self.calls["variable_info"] += 1
        if dcids != MMR:
            return {}
        return {
            MMR: {
                "provenanceSummary": {
                    "dc/base/UN_SDG": {"observationCount": 10, "seriesSummary": []},
                    "undata/p/SDG": {
                        "observationCount": 5592,
                        "timeSeriesCount": 233,
                        "seriesSummary": [
                            {
                                "earliestDate": "2000",
                                "latestDate": "2023",
                                "seriesKey": {"unit": UNIT_ID},
                            }
                        ],
                    },
                }
            }
        }

    def detect_and_fulfill(self, _t: object, question: str) -> dict[str, Any]:
        self.calls["detect_and_fulfill"] += 1
        guessed = "Bangladesh" not in question
        place = (
            {"dcid": "country/USA", "name": "United States of America"}
            if guessed
            else {"dcid": "country/BGD", "name": "Bangladesh"}
        )
        specs = {
            f"undata/unicef/CME_MR.AGE--{i}_multiple_place_bar_block": {
                "name": f"Child mortality rate [{i}]",
                "statVar": f"undata/unicef/CME_MR.AGE--{i}",
            }
            for i in range(10)
        }
        return {
            "place": place,
            "placeSource": "DEFAULT" if guessed else "CURRENT_QUERY",
            "config": {"categories": [{"statVarSpec": specs}]},
            "userMessages": ["Low confidence in understanding your query."] if guessed else [],
        }
