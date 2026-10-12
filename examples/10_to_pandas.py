"""A tidy pandas DataFrame with the source on every row. Needs: pip install pandas."""

import pandas as pd

import undata
from undata import _endpoints as api

VARIABLES = ["undata/sdg/SH_STA_MORT.SEX--F", "undata/sdg/EG_ACS_ELEC"]
PLACES = ["country/BGD", "country/NPL", "country/SSD"]

with undata.Transport() as t:
    body = api.series(t, VARIABLES, PLACES)

rows = []
for variable, by_entity in body["data"].items():
    for place in PLACES:
        block = by_entity.get(place, {})
        if not block.get("series"):
            print("no data:", variable, place)  # absent, not zero
            continue
        facet = body["facets"][block["facet"]]
        rows.extend(
            {
                "variable": variable,
                "place": place,
                "date": obs["date"],
                "value": obs["value"],
                "source": facet["provenanceId"],
                "unit": facet.get("unitDisplayName"),
                "provenance_url": facet.get("provenanceUrl"),
            }
            for obs in block["series"]
        )

df = pd.DataFrame(rows)
print(df.groupby(["variable", "place"])["date"].agg(["min", "max", "count"]))
