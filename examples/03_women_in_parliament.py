"""Women in parliament: who has passed 30%, and who has reached parity?"""

import undata as un

SEATS = "undata/sdg/SG_GEN_PARL.SEX--F"  # % of seats held by women, SDG 5.5.1

table = un.latest(SEATS, "Eastern Africa").sort_values("value", ascending=False)
print(table[["country", "year", "value"]].round(1).to_string(index=False), "\n")

thirty = table[table["value"] >= 30]
parity = table[table["value"] >= 50]
print(
    f"{len(thirty)} of the {len(table)} Eastern African parliaments with data have at least "
    f"30% women. {', '.join(parity['country'])} passed parity, with "
    f"{parity['value'].iloc[0]:.0f}% of seats held by women."
)
