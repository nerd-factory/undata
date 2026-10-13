"""Refugees by country of origin: the most in number is not the most per person."""

import undata as un

NUMBER = "undata/unicef/MG_RFGS_CNTRY_ORIGIN"  # refugees, by country of origin
PER_100K = "undata/sdg/SM_POP_REFG_OR"  # the same, per 100,000 population

# A region and a country together: Sudan is in Northern Africa in the UN's regions.
table = un.latest([NUMBER, PER_100K], ["Eastern Africa", "Sudan"])

for indicator, label in [(NUMBER, "Most refugees"), (PER_100K, "Most per 100,000 people")]:
    top = table[table["indicator"] == indicator].nlargest(5, "value")
    print(label)
    print(top[["country", "year", "value"]].to_string(index=False), "\n")

number = table[table["indicator"] == NUMBER].set_index("country")["value"]
rate = table[table["indicator"] == PER_100K].set_index("country")["value"]
print(
    f"{number.idxmax()} has the most refugees abroad ({number.max() / 1e6:.1f} million), but "
    f"relative to population {rate.idxmax()} is hit hardest: {rate.max():,.0f} refugees "
    f"for every 100,000 people, about one in {100_000 / rate.max():.0f}."
)
