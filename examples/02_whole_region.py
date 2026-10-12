"""Every African country in one request, and a check on which year each value is from."""

from collections import Counter

import undata
from undata import _endpoints as api

ELECTRICITY = "undata/sdg/EG_ACS_ELEC"  # % of population with access to electricity

with undata.Transport() as t:
    body = api.observation(t, ELECTRICITY, entity_expression=undata.child_countries_of("africa"))

latest = {
    place: block["orderedFacets"][0]["observations"][0]
    for place, block in body["byVariable"][ELECTRICITY]["byEntity"].items()
    if block.get("orderedFacets")
}
print(len(latest), "countries")
print("years:", dict(Counter(obs["date"] for obs in latest.values())))
for place, obs in sorted(latest.items(), key=lambda item: item[1]["value"])[:3]:
    print(f"{place:<12} {obs['date']}  {obs['value']}%")
