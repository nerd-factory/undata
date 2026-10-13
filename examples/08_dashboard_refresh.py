"""Refresh the numbers behind a dashboard. Schedule this file; nobody has to run it."""

from datetime import date

import undata as un

INDICATORS = [
    "undata/sdg/EG_ACS_ELEC",
    "undata/unicef/CME_MR.AGE--Y0T4",
    "undata/sdg/SG_GEN_PARL.SEX--F",
]

table = un.get(INDICATORS, "Southern Asia", years=(2015, date.today().year))
un.save(table, "dashboard-data.csv")  # Power BI, Tableau or Excel reads this file

print(
    f"{date.today()}: wrote {len(table)} rows for {table['country'].nunique()} countries, "
    f"{table['year'].min()} to {table['year'].max()}, to dashboard-data.csv"
)
