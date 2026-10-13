"""Are the least developed countries on track to cut maternal deaths by 2030?"""

import undata as un

# SDG 3.1.1, lower is better; 70 per 100,000 live births is the Target 3.1 level.
table = un.progress("3.1.1", "LDCs", better="lower", target=70)

columns = ["country", "status", "baseline_year", "baseline_value", "latest_value", "projected"]
print(table[columns].head(8).round(0).to_string(index=False), "\n")

un.chart(table, "ldc-progress.png")  # for the report
un.chart(table, "ldc-progress.html", interactive=True)  # hover for every number

print(un.describe(table))
