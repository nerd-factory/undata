"""Countries without data are named, never turned into zeros."""

import undata as un

table = un.latest("undata/sdg/VC_DTH_TOTR", ["Ukraine", "Norway", "Japan", "Mali"])

print(table[["country", "year", "value"]].to_string(index=False))
print("No data for:", [row["country"] for row in table.attrs["missing"]])
