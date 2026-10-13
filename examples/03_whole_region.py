"""A whole continent in one line. Regions stand for every country in them."""

import undata as un

table = un.latest("undata/sdg/EG_ACS_ELEC", "Africa")  # % with access to electricity

print(len(table), "countries, latest years:", sorted(table["year"].unique().tolist()))
print(table.nsmallest(3, "value")[["country", "year", "value", "unit"]].to_string(index=False))
