<div align="center">

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/nerd-factory/nerd-lab/main/assets/logo/nerd-lab-offwhite.svg">
  <source media="(prefers-color-scheme: light)" srcset="https://raw.githubusercontent.com/nerd-factory/nerd-lab/main/assets/logo/nerd-lab-ink.svg">
  <img alt="NERD LAB" src="https://raw.githubusercontent.com/nerd-factory/nerd-lab/main/assets/logo/nerd-lab-offwhite.svg" width="300">
</picture>

# undata

**A Python client for the UN System Data Commons that refuses to guess.**

[![CI](https://github.com/nerd-factory/undata/actions/workflows/ci.yml/badge.svg)](https://github.com/nerd-factory/undata/actions/workflows/ci.yml)
[![Live API contract](https://github.com/nerd-factory/undata/actions/workflows/live.yml/badge.svg)](https://github.com/nerd-factory/undata/actions/workflows/live.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue)](pyproject.toml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue)](LICENSE)

</div>

**[Use cases, with real output →](https://nerd-factory.github.io/undata/)**

> **Status: pre-alpha.** The foundation is built and tested; the friendly public API is
> not yet. Nothing is on PyPI. Read [PLAN.md](PLAN.md) for where this is going.
>
> **Unofficial.** A [Nerd Lab](https://github.com/nerd-factory) experiment. Not affiliated
> with or endorsed by the United Nations. The data belongs to the agencies that publish it.

## Why this exists

[data.un.org](https://data.un.org) unifies public statistics from 26 UN System entities
into one Data Commons knowledge graph. It is open — no key, no licence negotiation — and it
has three habits that make naive client code wrong in ways nobody notices:

1. **The official `datacommons-client` cannot fetch data from it.** The deployment's
   firewall answers `403 Forbidden` to any POST body containing a `"select"` key, and the
   observation endpoint needs one. That client always POSTs. undata uses GET.
2. **The search resolver always commits to a place.** Ask about child mortality in
   *Bengal* and you get a chart of the United States, titled as if nothing happened.
   undata will raise rather than substitute.
3. **Missing data is silently absent.** A country with no observations is simply not in
   the response, which is how a gap ends up charted as a zero. undata reports it.

There are eight more, documented in the
[UN Data Commons Field Guide](https://mafiatun.github.io/un-data-commons-field-guide/cookbook),
which is where this package's knowledge of the platform comes from.

## What works today

```bash
pip install "git+https://github.com/nerd-factory/undata"
```

```python
import undata
from undata import _endpoints as api  # low-level, will be wrapped by the public API

with undata.Transport() as t:
    body = api.observation(t, "Count_Person", entities=["country/BGD", "country/NPL"])

undata.parse_dcid("undata/sdg/VC_DTH_TOTN.AGE--Y0T17__SEX--F")
# ParsedDcid(namespace='undata', agency='sdg', code='VC_DTH_TOTN',
#            dimensions=(Dimension(name='AGE', value='Y0T17'), Dimension(name='SEX', value='F')))
```

- **Transport** — compact JSON bodies, GET for observations, percent-encoded relation
  expressions, retries with back-off on 429/5xx, and errors that explain themselves
  (a 403 tells you it is not an API key problem, because there are no API keys).
- **One wrapper per route** — observations, graph walks (with automatic paging past the
  500-value cap), resolve, series, variable search, variable info, place names, the
  variable-group tree, and the natural-language resolver.
- **The dcid grammar** — parse, build and describe variable identifiers.

Ten runnable scripts in [examples/](examples/) show what it can do today. They run against
the live API every night, and the [use-cases page](https://nerd-factory.github.io/undata/)
is built from them.

## What it will look like

```python
import undata as un

un.place.get("Bengal")  # raises PlaceNotFound with suggestions; never the USA
un.sdg.target("16.1").indicators()  # from a target your mandate names to fetchable variables
obs = un.data.fetch(variables, places=["BGD", "NPL"], time=range(2010, 2025))
obs.to_pandas()  # tidy, with provenance on every row
obs.missing  # the gaps, listed rather than hidden
obs.cite("apa")
```

The full design, the rules it enforces and the road to 1.0 are in [PLAN.md](PLAN.md).

## Developing

```bash
git clone https://github.com/nerd-factory/undata && cd undata
uv sync                     # Python 3.11+, installs dev tools
uv run pytest               # unit tests and doctests, offline
uv run pytest -m live       # pins the live platform's behaviour (network)
uv run ruff check . && uv run ruff format --check . && uv run mypy
```

See [CONTRIBUTING.md](CONTRIBUTING.md). Questions that feel too basic are welcome in
[Nerd Lab Discussions](https://github.com/nerd-factory/nerd-lab/discussions); they are not
too basic.

## Licence

Code: [MIT](LICENSE). Data fetched with it is governed by the
[UN Data Commons terms of use](https://data.un.org/undatacommons/terms-of-use) and by each
contributing agency's own terms.
