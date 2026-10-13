"""SDG 3.1: has maternal mortality fallen since 2015, and where is it below 70?"""

import undata as un

# The SDG indicator number works directly: 3.1.1 is the maternal mortality ratio.
change = un.change("3.1.1", "Southern Asia", 2015, 2023).sort_values("end_value")
print(change[["country", "start_value", "end_value", "change_pct"]].round(0).to_string(index=False))

# The regional and world figures, as published, to set the countries against.
print(
    un.totals("3.1.1", ["Southern Asia", "World"], years=2023)[["country", "value"]].round(0), "\n"
)

fell = int((change["change"] < 0).sum())
fell_in = f"all {fell}" if fell == len(change) else f"{fell} of the {len(change)}"
below = change.loc[change["end_value"] < 70, "country"].tolist()
print(
    f"Between 2015 and 2023, maternal mortality fell in {fell_in} countries of Southern Asia. "
    f"{len(below)} were below 70 deaths per 100,000 live births in 2023 ({', '.join(below)}), "
    "the level Target 3.1 sets for the world as a whole."
)
