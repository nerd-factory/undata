<div align="center">

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/nerd-factory/nerd-lab/main/assets/logo/nerd-lab-offwhite.svg">
  <source media="(prefers-color-scheme: light)" srcset="https://raw.githubusercontent.com/nerd-factory/nerd-lab/main/assets/logo/nerd-lab-ink.svg">
  <img alt="NERD LAB" src="https://raw.githubusercontent.com/nerd-factory/nerd-lab/main/assets/logo/nerd-lab-offwhite.svg" width="300">
</picture>

# undata

**UN data in Python, without the guessing.**

[![CI](https://github.com/nerd-factory/undata/actions/workflows/ci.yml/badge.svg)](https://github.com/nerd-factory/undata/actions/workflows/ci.yml)
[![Live API contract](https://github.com/nerd-factory/undata/actions/workflows/live.yml/badge.svg)](https://github.com/nerd-factory/undata/actions/workflows/live.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue)](https://github.com/nerd-factory/undata/blob/main/pyproject.toml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue)](https://github.com/nerd-factory/undata/blob/main/LICENSE)

**[Ten examples, with real output →](https://nerd-factory.github.io/undata/)**

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
| `un.search("words")` | Find indicators by what they measure. UN collections only, best match first. |
| `un.about(indicator)` | What an indicator is, whose it is, its unit, and which years it covers. |
| `un.get(indicator, countries, years)` | The numbers: one row per country and year, with unit and source. |
| `un.latest(indicator, countries)` | Each country's most recent value, with a warning if those years differ. |
| `un.countries(region)` · `un.regions()` | The names it knows, with UN names and ISO codes. |
| `un.sdg.goals()` · `targets(16)` · `indicators("16.1")` · `series("16.1.2")` | Walk from an SDG goal down to indicators you can fetch. |
| `un.ask("a question")` | See what data.un.org's search box decided, including whether it guessed the place. |
| `un.save(table, "file.xlsx")` · `un.cite(table)` | Save to Excel or CSV with sources; write citations for a report. |

Wherever a function asks for countries you can write names the way you would in an email
(`"Viet Nam"`, `"Vietnam"`, `"VNM"`), a list of them, or a region such as `"Southern Asia"`
or `"Africa"`. Every function explains itself: `help(un.get)`.

Every table has the same columns:

```
country  iso3  year  value  unit  indicator_name  indicator  source  source_url
```

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
  mentions Western Sahara (`ESH`, mistaken for a shell command). undata routes around both.

Each behaviour is pinned by a test in [tests/live/](https://github.com/nerd-factory/undata/tree/main/tests/live) that runs against the real
platform every night and opens an issue if the platform changes. Most of them were found
while writing the [UN Data Commons Field Guide](https://mafiatun.github.io/un-data-commons-field-guide/).

## Examples

Ten runnable scripts in [examples/](https://github.com/nerd-factory/undata/tree/main/examples): a first table, comparing a region, a whole
continent, an SDG target to its numbers, gaps, names, the search box, sources, Excel and
citations, and checking an indicator. They run against the live platform every night, and
[the examples page](https://nerd-factory.github.io/undata/) shows each with its real output.

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
