"""Who finishes primary school: the rural-urban gap in the Sahel and beyond."""

import undata as un

COMPLETION = "undata/sdg/SE_TOT_CPLR.EDUCATION_LEVEL--ISCED11_1"  # SDG 4.1.2, primary
COUNTRIES = ["Chad", "Niger", "Mali", "Nigeria", "Ghana", "Bangladesh", "Nepal"]

table = un.gap(COMPLETION, COUNTRIES, by="urbanization")  # rural against urban, same year

print(table.drop(columns=["iso3", "unit", "indicator", "source"]).round(2).to_string(index=False))
print()

un.chart(table, "rural-urban-gap.png")
print(un.describe(table))
