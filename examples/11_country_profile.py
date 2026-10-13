"""One page on Chad: where it stands against Middle Africa and the world."""

import undata as un

INDICATORS = [
    "3.1.1",  # maternal mortality
    "undata/sdg/SH_DYN_MORT.AGE--Y0T4",  # under-5 mortality, SDG 3.2.1
    "undata/sdg/SE_TOT_CPLR.EDUCATION_LEVEL--ISCED11_1",  # primary completion, 4.1.2
    "undata/sdg/EG_ACS_ELEC",  # access to electricity, 7.1.1
    "undata/sdg/SG_GEN_PARL.SEX--F",  # women in parliament, 5.5.1
]

table = un.profile("Chad", INDICATORS)

columns = ["indicator_name", "value", "year", "region_value", "world_value", "rank", "out_of"]
print(table[columns].round(1).to_string(index=False), "\n")

un.chart(table, "chad-profile.png")
print(un.describe(table))
