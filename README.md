<div align="center">

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/nerd-factory/nerd-lab/main/assets/logo/nerd-lab-offwhite.svg">
  <source media="(prefers-color-scheme: light)" srcset="https://raw.githubusercontent.com/nerd-factory/nerd-lab/main/assets/logo/nerd-lab-ink.svg">
  <img alt="NERD LAB" src="https://raw.githubusercontent.com/nerd-factory/nerd-lab/main/assets/logo/nerd-lab-ink.svg" width="300">
</picture>

# undata

**UN data in Python, without the guessing.**

[![CI](https://github.com/nerd-factory/undata/actions/workflows/ci.yml/badge.svg)](https://github.com/nerd-factory/undata/actions/workflows/ci.yml)
[![Live API contract](https://github.com/nerd-factory/undata/actions/workflows/live.yml/badge.svg)](https://github.com/nerd-factory/undata/actions/workflows/live.yml)
[![PyPI](https://img.shields.io/pypi/v/undata)](https://pypi.org/project/undata/)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue)](https://github.com/nerd-factory/undata/blob/main/pyproject.toml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue)](https://github.com/nerd-factory/undata/blob/main/LICENSE)

**[Nine use cases, with real output →](https://nerd-factory.github.io/undata/)**

</div>

Type a country's name, get a table. undata is a Python package for the
[UN System Data Commons](https://data.un.org), which holds statistics from 26 UN System
entities. It is written for colleagues who need numbers for a report, not a course in APIs.

> **Alpha.** It works today; the API may still change before 1.0.
> **Unofficial.** A [Nerd Lab](https://github.com/nerd-factory) experiment, not affiliated with
> or endorsed by the United Nations. The data belongs to the agencies that publish it.

## Three lines to a spreadsheet

```bash
pip install undata
```

```python
import undata as un

table = un.get("undata/sdg/SH_STA_MORT.SEX--F", ["Bangladesh", "Viet Nam"])
un.save(table, "maternal-mortality.xlsx")  # data on one sheet, citations on the next
```

In Google Colab, run `!pip install undata` in the first cell. For the latest unreleased
changes: `pip install "git+https://github.com/nerd-factory/undata"`.

Don't know the indicator's id? `un.search("maternal mortality")` lists matching indicators
with their names. Copy the id from the first column.

## Everything on one screen

| Function | What it does |
|---|---|
| `un.search("words")` | Find indicators by what they measure: UN collections, one row per indicator, with coverage. |
| `un.about(indicator)` | What an indicator is, whose it is, its unit, years, and its SDG metadata link. |
| `un.get(indicator, countries, years)` | The numbers: one row per country and year, with unit and source. `by="sex"` for a breakdown, `wide=True` for one column per indicator. |
| `un.latest(indicator, countries)` | Each country's most recent value. `within=10` keeps only values from the past ten years and names the countries whose latest is older. |
| `un.coverage(table)` | How complete a table is: who has a value, who was too old, who has none, and which years. |
| `un.totals(indicator, ["World", "LDCs"])` | The official figure for a region or group, as the agency published it. |
| `un.change(indicator, countries, 2015, 2023)` | Before, after, the difference and the percentage change. |
| `un.compare({"a": id1, "b": id2}, countries)` | Indicators side by side, with who has which spelled out. |
| `un.breakdowns(indicator)` | Every breakdown: by sex, age, wealth and so on. |
| `un.countries(region)` · `un.regions()` | The UN M49 list: countries and areas with their UN names, M49 regions, and the LDC, LLDC and SIDS groups. |
| `un.sdg.goals()` · `targets(16)` · `indicators("16.1")` · `series("16.1.2")` | Walk from an SDG goal down to indicators you can fetch. |
| `un.describe(table)` | Plain-English sentences about a table, worked out from its numbers. |
| `un.chart(table)` | A chart with its source underneath, for a slide. Needs `pip install "undata[charts]"`. |
| `un.save(table, "file.xlsx")` · `un.cite(table)` | Excel or CSV with sources; citations for a report. |
| `un.for_ai(table, task="brief")` | The table with its sources, caveats and a task, to paste into an AI assistant. |
| `un.ai_pack(table, "pack.zip")` | The data, a data dictionary and a prompt, to upload to an AI assistant. |
| `un.powerquery(indicator, countries)` | Power Query code that fetches the same data in Power BI or Excel. |
| `un.ask("a question")` | What data.un.org's search box decided, including whether it guessed the place. |
| `un.configure(cache=True)` | Keep responses on disk, for slow connections and notebooks that run again. |

Wherever a function asks for countries you can write names the way you would in an email
(`"Viet Nam"`, `"Vietnam"`, `"VNM"`), a list of them, a region such as `"Southern Asia"`
or `"Africa"`, or a UN group: `"LDCs"`, `"LLDCs"`, `"SIDS"`. Wherever it asks for an
indicator, an SDG number such as `"3.1.1"` works when one series reports it. Every
function explains itself: `help(un.get)`.

### From a terminal

The same, without writing Python:

```bash
undata search "maternal mortality"
undata totals 3.1.1 World LDCs SIDS --latest
undata change 3.1.1 "Southern Asia" --start 2015 --end 2023 --describe
undata get 3.1.1 LDCs --years 2015-2023 --to maternal-mortality.xlsx
undata powerquery 3.1.1 "Southern Asia" > query.m
```

Every table has the same columns:

```
country  iso3  year  value  unit  indicator_name  indicator  source  source_url
```

## The country list is the UN's own

Countries, regions and groups come from **UN M49**, the UN Statistics Division's
standard, shipped with the package and checked against the UN's current table every
night. Tables use official UN names, regions follow M49, and the LDC, LLDC and SIDS
groups are the current UN lists (44, 32 and 53 countries), not the platform's older
copies. Places the platform holds outside M49 are left out of every list, region and
group; they can still be asked for by platform code, such as `country/XKS`.

## Taking it to an AI assistant

```python
table = un.latest("3.1.1", "LDCs", within=10)
un.ai_pack(table, "maternal-mortality.zip")   # upload, then paste prompt.md
print(un.for_ai(table, task="brief"))         # or paste this as one message
```

The pack holds `data.csv`, `metadata.md` (what each column means; each indicator's
unit, source and citation; how complete the data is; the caveats) and `prompt.md`
(rules that keep the assistant to these numbers, and a task). Tasks: `explain`,
`brief`, `trends`, `gaps`, `chart`.

## The careful parts are built in

- **It never guesses a place.** data.un.org's search box answers a question about "Bengal"
  with figures for the United States. undata stops and says it does not know "Bengal".
- **Gaps are named, never zero.** Countries without data are left out of the table and listed
  in a `MissingDataWarning`, so a chart cannot show them as zeros.
- **UN names in, UN names out.** Tables say Türkiye, Viet Nam and Côte d'Ivoire, whatever
  spelling you typed.
- **The source is on every row.** The same statistic can come from several agencies with
  different numbers.
- **Mixed years are flagged.** "Latest" means each country's own latest year; a
  `MixedYearsWarning` says when those differ.
- **It works where other clients fail.** The platform's firewall blocks Google's official
  `datacommons-client` (any POST body containing `"select"`) and any GET request that
  mentions Western Sahara, Greece or Slovenia (`ESH`, `GRC`, `SVN`, mistaken for
  command names). undata routes around all of them.

Each behaviour is pinned by a test in [tests/live/](https://github.com/nerd-factory/undata/tree/main/tests/live) that runs against the real
platform every night and opens an issue if the platform changes. Most of them were found
while writing the [UN Data Commons Field Guide](https://mafiatun.github.io/un-data-commons-field-guide/).

## Use cases

Nine requests as they arrive in UN work, each a runnable script in
[examples/](https://github.com/nerd-factory/undata/tree/main/examples) that ends with a
sentence ready for the report:

| # | Who | What |
|---|---|---|
| 01 | Resident Coordinator's Office | A briefing note: Chad against its Sahel neighbours |
| 02 | SDG reporting | Maternal mortality in Southern Asia since 2015, against the Target 3.1 level |
| 03 | Gender focal point | Women in parliament in Eastern Africa: who has passed 30%, who reached parity |
| 04 | Humanitarian coordination | Refugees by country of origin, in number and per person |
| 05 | Peace and security | Conflict deaths against homicide, and who reports at all |
| 06 | Statistics focal point | One statistic, three agencies, two numbers: what to cite |
| 07 | Publications team | A regional data pack in Excel, with citations and gaps on their own sheets |
| 08 | Monitoring and evaluation | A dashboard file that refreshes itself on a schedule |
| 09 | Communications | Checking what data.un.org's search box decided before sharing its chart |

They run against the live platform every night. [The use-cases page](https://nerd-factory.github.io/undata/)
shows each with its code, a chart, the real output and the sentence.

## For developers

The friendly functions sit on three layers you can use directly: `undata.Transport` (the
only code that touches the network), `undata._endpoints` (one thin wrapper per API route),
and `undata.dcid` (the identifier grammar). [PLAN.md](https://github.com/nerd-factory/undata/blob/main/PLAN.md) covers the design and the
road to 1.0.

```bash
git clone https://github.com/nerd-factory/undata && cd undata
uv sync                     # Python 3.11+, installs dev tools
uv run pytest               # unit tests and doctests, offline
uv run pytest -m live       # pins the live platform's behaviour (network)
uv run ruff check . && uv run ruff format --check . && uv run mypy
```

See [CONTRIBUTING.md](https://github.com/nerd-factory/undata/blob/main/CONTRIBUTING.md). Questions that feel too basic are welcome in
[Nerd Lab Discussions](https://github.com/nerd-factory/nerd-lab/discussions); they are not
too basic.

## Licence

Code: [MIT](https://github.com/nerd-factory/undata/blob/main/LICENSE). Data fetched with it is governed by the
[UN Data Commons terms of use](https://data.un.org/undatacommons/terms-of-use) and by each
contributing agency's own terms.
