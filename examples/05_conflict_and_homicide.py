"""Conflict deaths in context: who reports them, and how they compare with homicide."""

import undata as un

CONFLICT = "undata/sdg/VC_DTH_TOTR"  # conflict-related deaths per 100,000, SDG 16.1.2
HOMICIDE = "undata/sdg/VC_IHR_PSRC"  # intentional homicide per 100,000, SDG 16.1.1

# Ask for the whole world. The warning lists who has no data: absent, not zero.
reporting = un.latest(CONFLICT, "World")["country"].tolist()

both = un.latest([CONFLICT, HOMICIDE], reporting)
wide = both.pivot(index="country", columns="indicator", values="value")
wide = wide.rename(columns={CONFLICT: "conflict", HOMICIDE: "homicide"})
wide = wide[["conflict", "homicide"]].sort_values("conflict", ascending=False)
print(wide.round(1).to_string(), "\n")

higher = wide.index[wide["conflict"] > wide["homicide"]].tolist()
print(
    f"Only {len(reporting)} countries report conflict-related deaths. In {len(higher)} of "
    f"them, conflict killed more people per 100,000 than homicide: {', '.join(higher)}."
)
