"""A data pack for the publications team: three indicators, one Excel file, sources included."""

import pandas as pd

import undata as un

INDICATORS = [
    "undata/sdg/EG_ACS_ELEC",  # access to electricity
    "undata/sdg/SH_H2O_SAFE",  # safely managed drinking water
    "undata/sdg/SE_TOT_CPLR.EDUCATION_LEVEL--ISCED11_1",  # primary completion
]

table = un.latest(INDICATORS, "South-Eastern Asia")
path = un.save(table, "south-eastern-asia-data-pack.xlsx")

sheets = pd.ExcelFile(path).sheet_names
print(f"Saved {len(table)} values for {table['country'].nunique()} countries to {path}")
print("Sheets:", ", ".join(sheets), "\n")
print(un.cite(table))
