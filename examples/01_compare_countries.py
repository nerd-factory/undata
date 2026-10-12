"""Compare South Asian countries on the Human Development Index."""

import undata
from undata import _endpoints as api

HDI = "undata/undphdro/HDI_hdi"
COUNTRIES = ["country/BGD", "country/IND", "country/LKA", "country/NPL", "country/PAK"]

with undata.Transport() as t:
    body = api.observation(t, HDI, entities=COUNTRIES)

rows = []
for place, block in body["byVariable"][HDI]["byEntity"].items():
    latest = block["orderedFacets"][0]["observations"][0]
    rows.append((latest["value"], place, latest["date"]))

for value, place, year in sorted(rows, reverse=True):
    print(f"{place:<12} {year}  {value:.3f}")
