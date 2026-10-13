"""Save to Excel with a sheet of citations, and cite the data in a report."""

import undata as un

table = un.get("undata/sdg/SH_STA_MORT.SEX--F", "Southern Asia", years=(2015, 2023))

un.save(table, "maternal-mortality.xlsx")  # sheets: data, sources
print(un.cite(table))
