"""One statistic, three agencies. Quote one figure, and name whose it is."""

import undata as un

MATERNAL_MORTALITY_RATIO = [
    "undata/sdg/SH_STA_MORT.SEX--F",  # Global SDG Indicators Database
    "undata/unicef/MNCH_MMR.SEX--F",  # UNICEF
    "undata/undphdro/GII_mmr.SEX--F",  # UNDP Human Development Report Office
]
table = un.latest(MATERNAL_MORTALITY_RATIO, "Bangladesh")
print(table[["source", "year", "value"]].round(1).to_string(index=False), "\n")

low, high = table["value"].min(), table["value"].max()
odd = table.loc[table["value"].idxmax(), "source"]
print(
    f"For Bangladesh in {table['year'].max()}, the three sources give {low:.0f} to {high:.0f} "
    f"maternal deaths per 100,000 live births; {odd} is the outlier. A gap of "
    f"{(high / low - 1) * 100:.0f}% is enough to change a headline, so cite the source."
)
