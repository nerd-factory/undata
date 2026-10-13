"""Your first table: find an indicator by name, then get it for two countries."""

import undata as un

# 1. Find the indicator. Copy its id from the "indicator" column.
print(un.search("maternal mortality").head(3).to_string(index=False))

# 2. Get it. Country names work as you would write them.
table = un.get("undata/sdg/SH_STA_MORT.SEX--F", ["Bangladesh", "Viet Nam"], years=(2020, 2023))
print(table[["country", "year", "value", "unit"]].to_string(index=False))
