"""From an SDG target your mandate names, to the numbers."""

import undata as un

print(un.sdg.indicators("16.1").to_string(index=False))

series = un.sdg.series("16.1.2")
print(series[series["total"]][["indicator", "name"]].to_string(index=False))

rates = un.latest("undata/sdg/VC_DTH_TOTR", ["Ukraine", "Sudan", "Myanmar"])
print(rates[["country", "year", "value"]].to_string(index=False))
