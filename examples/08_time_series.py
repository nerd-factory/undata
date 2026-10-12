"""A full time series per country, for a trend line."""

import undata
from undata import _endpoints as api

MMR = "undata/sdg/SH_STA_MORT.SEX--F"  # maternal deaths per 100,000 live births

with undata.Transport() as t:
    body = api.series(t, MMR, ["country/BGD", "country/NOR"])

for place, block in body["data"][MMR].items():
    first, last = block["series"][0], block["series"][-1]
    print(
        f"{place:<12} {len(block['series'])} years   "
        f"{first['date']}: {first['value']:.1f}  ->  {last['date']}: {last['value']:.1f}"
    )
