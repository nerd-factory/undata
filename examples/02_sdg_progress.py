"""SDG 3.1: has maternal mortality fallen since 2015, and where is it below 70?"""

import undata as un

# From the indicator your mandate names to the series that reports it.
print(un.sdg.series("3.1.1")[["indicator", "name"]].to_string(index=False), "\n")

MMR = "undata/sdg/SH_STA_MORT.SEX--F"
table = un.get(MMR, "Southern Asia", years=[2015, 2023])

change = table.pivot(index="country", columns="year", values="value")
change["change %"] = (change[2023] / change[2015] - 1) * 100
print(change.sort_values(2023).round(0).to_string(), "\n")

fell = int((change["change %"] < 0).sum())
fell_in = f"all {fell}" if fell == len(change) else f"{fell} of the {len(change)}"
below = change.index[change[2023] < 70].tolist()
print(
    f"Between 2015 and 2023, maternal mortality fell in {fell_in} countries "
    f"of Southern Asia. {len(below)} were below 70 deaths per 100,000 live births in 2023 "
    f"({', '.join(below)}), the level Target 3.1 sets for the world as a whole."
)
