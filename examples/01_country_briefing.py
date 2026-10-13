"""Briefing note: Chad against its Sahel neighbours, in one table and one sentence."""

import undata as un

SAHEL = ["Chad", "Niger", "Mali", "Burkina Faso", "Mauritania", "Sudan"]
MEASURES = {
    "electricity %": "undata/sdg/EG_ACS_ELEC",
    "under-5 deaths per 1,000": "undata/unicef/CME_MR.AGE--Y0T4",
    "primary completion %": "undata/sdg/SE_TOT_CPLR.EDUCATION_LEVEL--ISCED11_1",
}

# One row per country, a value and a year per measure.
brief = un.compare(MEASURES, SAHEL).set_index("country")
print(brief.drop(columns="iso3").round(1).to_string(), "\n")

# The sentence for the note, worked out from the numbers rather than typed in.
RANK = {1: "", 2: "second-", 3: "third-", 4: "fourth-", 5: "fifth-", 6: "sixth-"}
chad = brief.loc["Chad"]
power_rank = int(brief["electricity %"].rank()["Chad"])  # 1 = the lowest
deaths_rank = int(brief["under-5 deaths per 1,000"].rank(ascending=False)["Chad"])  # 1 = highest
print(
    f"In {chad['electricity % year']}, {chad['electricity %']:.0f}% of people in Chad had "
    f"electricity, the {RANK[power_rank]}lowest of the six Sahel countries compared, and "
    f"{chad['under-5 deaths per 1,000']:.0f} of every 1,000 children died before their fifth "
    f"birthday, the {RANK[deaths_rank]}highest."
)
