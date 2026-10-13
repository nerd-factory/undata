"""One statistic, three agencies. The source column says whose number you are using."""

import undata as un

MATERNAL_MORTALITY_RATIO = [
    "undata/sdg/SH_STA_MORT.SEX--F",  # Global SDG Indicators Database
    "undata/unicef/MNCH_MMR.SEX--F",  # UNICEF
    "undata/undphdro/GII_mmr.SEX--F",  # UNDP Human Development Report Office
]
table = un.latest(MATERNAL_MORTALITY_RATIO, "Bangladesh")

print(table[["source", "year", "value"]].to_string(index=False))
