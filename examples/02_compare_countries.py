"""Compare the countries of a region on one indicator, each at its latest year."""

import undata as un

table = un.latest("undata/undphdro/HDI_hdi", "Southern Asia")

ranked = table.sort_values("value", ascending=False)
print(ranked[["country", "year", "value"]].to_string(index=False))
