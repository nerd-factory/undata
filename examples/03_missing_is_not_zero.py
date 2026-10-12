"""Count who reports before you join two indicators. Absent is not zero."""

import undata
from undata import _endpoints as api

GDP_PER_CAPITA = "undata/unicef/SPP_GDPPC"
CONFLICT_DEATH_RATE = "undata/sdg/VC_DTH_TOTR"  # SDG 16.1.2, per 100,000
EVERY_COUNTRY = undata.child_countries_of("Earth")


def reporting(t: undata.Transport, variable: str) -> set[str]:
    body = api.observation(t, variable, entity_expression=EVERY_COUNTRY)
    by_entity = body["byVariable"][variable]["byEntity"]
    return {place for place, block in by_entity.items() if block.get("orderedFacets")}


with undata.Transport() as t:
    gdp = reporting(t, GDP_PER_CAPITA)
    conflict = reporting(t, CONFLICT_DEATH_RATE)

print("GDP per capita:     ", len(gdp), "countries")
print("Conflict death rate:", len(conflict), "countries")
print("Both:               ", len(gdp & conflict))
print("Norway in the conflict series?", "country/NOR" in conflict)
