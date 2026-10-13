"""Conflict deaths in context: who reports them, and how they compare with homicide."""

import undata as un

INDICATORS = {
    "conflict": "undata/sdg/VC_DTH_TOTR",  # conflict-related deaths per 100,000, SDG 16.1.2
    "homicide": "undata/sdg/VC_IHR_PSRC",  # intentional homicide per 100,000, SDG 16.1.1
}

# Ask for the whole world. The warning says how many countries have both: few.
table = un.compare(INDICATORS, "World")
reporting = table[table["conflict"].notna()].sort_values("conflict", ascending=False)
print(reporting[["country", "conflict", "homicide"]].round(1).to_string(index=False), "\n")

higher = reporting.loc[reporting["conflict"] > reporting["homicide"], "country"].tolist()
print(
    f"Only {len(reporting)} countries report conflict-related deaths. In {len(higher)} of "
    f"them, conflict killed more people per 100,000 than homicide: {', '.join(higher)}."
)
