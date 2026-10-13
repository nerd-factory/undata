"""Briefing note: Chad against its Sahel neighbours, in one table and one sentence."""

import undata as un

SAHEL = ["Chad", "Niger", "Mali", "Burkina Faso", "Mauritania", "Sudan"]
MEASURES = {
    "undata/sdg/EG_ACS_ELEC": "electricity %",
    "undata/unicef/CME_MR.AGE--Y0T4": "under-5 deaths per 1,000",
    "undata/sdg/SE_TOT_CPLR.EDUCATION_LEVEL--ISCED11_1": "primary completion %",
}

table = un.latest(list(MEASURES), SAHEL)
table["measure"] = table["indicator"].map(MEASURES)
brief = table.pivot(index="country", columns="measure", values="value")
print(brief[list(MEASURES.values())].round(1).to_string(), "\n")

# The sentence for the note, worked out from the numbers rather than typed in.
RANK = {1: "", 2: "second-", 3: "third-", 4: "fourth-", 5: "fifth-", 6: "sixth-"}
chad = table[table["country"] == "Chad"].set_index("measure")
power, deaths = chad.loc["electricity %"], chad.loc["under-5 deaths per 1,000"]
# Rank 1 means the lowest electricity, and the highest child mortality.
power_rank = int(brief["electricity %"].rank()["Chad"])
deaths_rank = int(brief["under-5 deaths per 1,000"].rank(ascending=False)["Chad"])
print(
    f"In {power.year}, {power.value:.0f}% of people in Chad had electricity, the "
    f"{RANK[power_rank]}lowest of the six Sahel countries compared, and {deaths.value:.0f} of "
    f"every 1,000 children died before their fifth birthday, the {RANK[deaths_rank]}highest."
)
