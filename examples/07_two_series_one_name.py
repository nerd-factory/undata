"""Search hands you a series. Check whose it is before you publish a number from it."""

import undata
from undata import _endpoints as api

with undata.Transport() as t:
    hits = [hit["dcid"] for hit in api.stat_var_search(t, "maternal mortality")["statVars"]]
    un_series = "undata/sdg/SH_STA_MORT.SEX--F"
    print("top hit:      ", hits[0])
    print("UN series at: ", f"#{hits.index(un_series) + 1} of {len(hits)}")
    print()

    body = api.series(t, [hits[0], un_series], ["country/BGD"])

for variable, by_entity in body["data"].items():
    block = by_entity["country/BGD"]
    last = block["series"][-1]
    source = body["facets"][block["facet"]]["provenanceId"]
    print(f"{variable:<30} {last['date']}  {last['value']:.1f}  source: {source}")
