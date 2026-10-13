# The plan

How undata becomes the package developers reach for when they need UN data in Python.
This is a living document: when a decision changes, change it here in the same pull
request.

## 1. What "go-to" has to mean

1. **Three lines to a correct DataFrame**, with no identifiers needed to start.
2. **Safe by default.** Never substitute a place, never turn a gap into a zero, never
   drop provenance.
3. **One way to do each thing.** The same verbs across places, variables, SDGs and
   sources, the way wbgapi uses `list`, `get` and `info` everywhere.
4. **Errors that say what to do next.** A 403 explains the firewall. An unknown place
   suggests the places it might mean.
5. **Native where people work:** notebook tables, type hints and autocomplete, pandas
   and polars, sync and async.
6. **Trustworthy engineering:** strict tests, a nightly check against the live API,
   and releases traceable to their source.
7. **Documented by example**, and every example runs in CI.

## 2. The platform, as verified

| Route | Purpose | Gotcha |
|---|---|---|
| `/core/api/v2/observation` | Values | **GET only.** A POST body with `"select"` gets 403. |
| `/core/api/v2/node` | Graph walks | 500 values per page, then `nextToken`. `->`, `<-`, `+` must be percent-encoded. |
| `/core/api/v2/resolve` | Names to dcids | |
| `/api/observations/series` | Full series per variable × place | Missing places are absent, not empty. |
| `/api/stats/stat-var-search` | Variable search | Ranks Data Commons' older copy (`sdg/...`, from `dc/base/UN_SDG`) above the UN's own series (`undata/sdg/...`). For maternal mortality the UN series is result 23 of 65. |
| `/api/variable/info` | Coverage and provenance summary | |
| `/api/place/name` | Place display names | |
| `/api/variable-group/info` | Category tree with counts | POST |
| `/api/explore/detect-and-fulfill` | Natural-language resolver | Silently supplies a place when it recognises none. |

Any POST body containing a line break also gets 403. In query strings the server reads
`+` literally rather than as a space. `tests/live/` pins all of this
nightly.

## 3. Public API

> **Update, 2026-10-13.** The friendly API below shipped with a flatter, simpler shape
> than first sketched, because the main audience is UN colleagues with little data
> experience: `un.get(indicator, countries, years)`, `un.latest`, `un.search`,
> `un.about`, `un.countries`, `un.regions`, `un.sdg.*`, `un.ask`, `un.save`, `un.cite`.
> See the README for the current list. The sketch is kept for the parts not built yet.

```python
import undata as un

# Discover
un.search("child mortality")  # ranked variables, UN collections first
un.sdg.goals()
un.sdg.target("16.1").indicators()  # framework to fetchable variables
un.variable.get("undata/sdg/SH_STA_MORT.SEX--F")
un.variable.info(...)  # name, agency, unit, dimensions, coverage, sources
un.variable.disaggregations("undata/sdg/VC_DTH_TOTN")  # every slice, including "unknown"
un.source.list()  # the contributing collections

# Places: strict by default
un.place.get("BGD")  # ISO3, M49, exact name or dcid
un.place.get("Bengal")  # PlaceNotFound with suggestions
un.place.countries(within="africa")  # one server-side query
un.place.regions(scheme="sdg")

# Data
obs = un.data.fetch(variables, places=["BGD", "NPL"], time=range(2010, 2025))
obs.to_pandas()  # tidy, provenance columns included
obs.to_polars()
obs.wide()
obs.missing  # requested pairs with no data, listed explicitly
obs.sources
obs.cite("apa")  # also chicago, bibtex, plain
un.data.frame(...)  # fetch(...).to_pandas()
un.data.latest(variable, places)  # warns when "latest" spans many years

# The resolver, made inspectable
r = un.ask("child mortality in Bengal")
r.place, r.place_was_inferred  # country/USA, True (and a warning)

# Escape hatches and configuration
un.graph.node("undata/g/sdgf/target-16-1", "->*")
un.raw.observation(...)
client = un.Client(timeout=30, cache="~/.cache/undata")
async with un.AsyncClient() as ac:
    ...
```

**Design rules**

- **A client underneath.** Module-level functions use a shared default client, the way
  `httpx.get` does. Tests and alternative deployments create their own.
- **Rich, frozen dataclasses:** `Place`, `Variable`, `Observation`, `Source`,
  `SDGTarget`, `Resolution`. Each renders as a table in Jupyter (`_repr_html_`) and
  prints readably in a terminal.
- **Accept anything, return one shape.** Any argument takes a single value or a list,
  as an ISO3 code, M49 code, name or dcid.
- **Fixed tidy columns:** `variable, variable_name, place, place_name, date, value,
  unit, source, facet_id, provenance_url, measurement_method`. The citation is stored
  in `df.attrs`.
- **Core dependency is `httpx` only.** pandas, polars and the command-line tool are
  optional extras.
- **Command-line tool** as the `[cli]` extra: `undata search`, `undata get ... --csv`,
  `undata cite`.

## 4. Architecture

```
src/undata/
  __init__.py      public re-exports, default client
  _client.py       Client / AsyncClient: config, pool, cache            (planned)
  _http.py         transport: retries, encoding, explanatory errors      (done)
  _endpoints.py    one wrapper per route, paging                         (done)
  dcid.py          identifier grammar                                    (done)
  place.py variable.py sdg.py source.py data.py search.py ask.py cite.py graph.py
  _models.py _display.py _frames.py
  errors.py        exception hierarchy                                   (started)
  warnings.py      warning classes                                       (planned)
  cli.py                                                                 (planned)
```

There are four layers, and each may only call the one below it:

1. **Transport.** The only module that touches the network.
2. **Endpoints.** Raw wrappers that return the API's JSON as-is.
3. **Domain modules.** Where the rules in section 5 are enforced.
4. **Display and export.**

## 5. Rules the package enforces

| Platform behaviour | Package behaviour |
|---|---|
| POST with `select` gets 403 | GET-only observations. `BlockedRequestError` explains that no API key exists. |
| A line break in a POST body gets 403 | Compact JSON always, and a test pins it. |
| An unencoded relation expression gets 400 | Encoded in the transport. A test pins `+` as `%2B`. |
| The resolver supplies a place silently | `ask()` exposes `place_was_inferred` and raises `InferredPlaceWarning`. `place.get` is strict. |
| Missing data is absent from responses | `obs.missing`. `include_missing=True` adds NaN rows. Never zero. |
| "Latest" means a different year per place | `VintageSpreadWarning`, and a `date` column on every row. |
| Graph walks are capped at 500 values | Pages are followed automatically. `TruncatedResultWarning` if the cap is hit anyway. |
| The bare code may not be the total | `variable.get` suggests the slices that do exist. |
| Age/sex slices leave out "unknown" | `disaggregations()` includes `_U` and says the named slices won't sum to the total. |
| One indicator under two agencies | `DuplicateSourceWarning`. `info()` lists them as related. |
| Sub-national queries return dependent territories | `SubnationalArtefactWarning`. |
| Search ranks the older base copy above the UN series | `search` ranks `undata/` results first and labels every result with its source. |
| `+` in a query string is read literally | Spaces are sent as `%20`, and a test pins it. |

Every warning class can be silenced individually.

## 6. Testing

| Layer | Tool |
|---|---|
| Unit and logic | pytest, plus hypothesis for dcid round-trips |
| HTTP behaviour | respx |
| Recorded real responses | pytest-recording (cassettes) |
| Live platform contract | `pytest -m live`, run nightly; opens an issue on failure |
| Docs | doctests on modules; pytest-examples on the docs site |
| Types | `mypy --strict`, plus `assert_type` tests on the public API |
| Minimum dependencies | `uv sync --resolution lowest-direct` |
| Notebooks | nbmake on the examples gallery |

Coverage targets: 90% or more overall, and 100% on `dcid.py` and the rules in
section 5.

## 7. Tooling

- **Build:** uv, hatchling, and hatch-vcs (the version comes from the git tag).
- **Python:** 3.11 through 3.14, with 3.15 added when it ships. Versions are dropped on
  the community's SPEC 0 schedule.
- **Code quality:** ruff for linting and formatting, and `mypy --strict`.
- **Upkeep:** Dependabot for GitHub Actions and Python dependencies.
- **Planned:** pre-commit hooks, typos, CodeQL and an OpenSSF Scorecard.
- **Licence:** MIT, matching the rest of Nerd Lab. The data's own terms are separate.

## 8. Documentation

The docs site will use MkDocs Material, with mkdocstrings for the reference and mike
for versioning. It will be published at `nerd-factory.github.io/undata`.

- **Tutorials:** your first DataFrame; from an SDG target to a chart; comparing
  countries honestly.
- **How-to guides:** a whole region in one call; disaggregations; citations; async; the
  Python step in Power BI; caching.
- **Reference:** generated from docstrings. Every public function has a runnable
  example.
- **Explanation:** how the platform works; the thirteen traps; why the package uses GET;
  how it compares with `datacommons-client` and wbgapi.

Also planned:

- **`llms.txt` and a one-page API summary**, so AI coding assistants write correct
  undata code.
- **A notebook gallery** with "Open in Colab" links.
- **The field guide's Python recipes** moved onto undata.

## 9. Release engineering

| Workflow | Trigger | What it does |
|---|---|---|
| `ci.yml` | push, pull request | Lint and types; tests on 3 operating systems × 4 Pythons; lowest-dependency run; wheel build and smoke import |
| `live.yml` | nightly | Platform contract; opens a `platform-change` issue on failure |
| `release.yml` | `v*` tag | Builds once, publishes to TestPyPI then PyPI, then creates the GitHub release |
| `docs.yml` | push to main, tags | Builds and deploys the versioned docs (planned) |

**Publishing:**

- **No tokens.** PyPI's trusted publishing accepts uploads straight from the release
  workflow.
- **Provenance.** PyPI records which workflow built each file.
- **Approval.** The `pypi` environment needs a maintainer's approval before upload.

**Versioning:**

- **Semantic versioning,** staying on 0.x until the API settles.
- **Deprecations:** anything removed gets a `DeprecationWarning` for at least one minor
  release first.
- **Changelog:** Keep a Changelog format.

**Install routes:**

- `pip install undata`
- `pip install "undata[pandas]"`
- `pip install git+https://github.com/nerd-factory/undata@vX.Y.Z`
- conda-forge, from 0.3

## 10. Roadmap

Estimates assume part-time work, about 15 hours a week.

| Phase | Weeks | Delivers |
|---|---|---|
| 0. Decisions | 0 | Repo, name, licence ✅. Still to do: register the trusted publishers on pypi.org and test.pypi.org. |
| 1. Foundation | 1–2 | Tooling, CI, transport, endpoints, dcid, live contract ✅. Recorded response cassettes still to do. |
| 2. Data core | 2–4 | ✅ Shipped as the friendly API: `un.get`, `un.latest`, strict places with UN names, missing-data and mixed-year warnings, `save`, `cite`. Next: tag **0.1.0** and publish to PyPI. |
| 3. Discovery | 4–6 | ✅ `search`, `about`, `sdg`, `ask` shipped. Still to do: `disaggregations`, polars output, async client, on-disk cache, command-line tool → **0.2.0** |
| 4. Experience | 6–8 | Notebook and terminal display, `cite`, the command-line tool, async, cache → **0.3.0**, then conda-forge |
| 5. Docs and hardening | 8–10 | Docs site, notebook gallery, `llms.txt`, performance → **0.4.0 beta** |
| 6. Stability | 10–14 | API changes from feedback; pyOpenSci review → **1.0.0** |

## 10a. Shipped in 0.2 (2026-10-13)

The review of what users needed beyond the platform's own API became 0.2: UN groupings
(LDCs, LLDCs, SIDS), official regional totals, SDG numbers as input, wide tables, a
freshness cut-off, change over time, honest comparisons, breakdowns, plain-English
summaries, charts, AI-ready export, Power Query generation, SDG metadata links, better
search, a disk cache and a command-line tool. Still open: async, polars output, and the
naming decision for Taiwan and Kosovo, which the platform names in its own way.

## 11. Requirements for 1.0

- [ ] Every public function is typed, documented and has a runnable example
- [ ] Every rule in section 5 is covered by an offline test and by the live contract
- [ ] Coverage of 90% or more; ruff and `mypy --strict` pass with no exceptions
- [ ] Tested on Linux, macOS and Windows with Python 3.11–3.14
- [ ] Docs site live
- [ ] On PyPI with provenance, and on conda-forge
- [ ] Zenodo DOI per release; `CITATION.cff`
- [ ] The 403 reported to UNSD, and a GET fallback offered upstream to `datacommons-client`
- [ ] pyOpenSci review submitted

## 12. Decisions

| Decision | Choice | Notes |
|---|---|---|
| Name | `undata` | Free on PyPI as of 2026-10-12 |
| Home | `nerd-factory/undata` | A Nerd Lab experiment |
| Status | Unofficial | Said in the README and on PyPI. Revisit if UNSD wants to endorse it. |
| Licence | MIT | Matches the rest of Nerd Lab |
| Models | dataclasses | Keeps the install light; no pydantic |
| Audience | UN colleagues with little data experience first | Decided 2026-10-13. Flat namespace (`un.get`), names not ids for places, tables not JSON, plain-English warnings. |
| pandas, openpyxl | Required, not extras | Every result is a table and Excel is the common destination; an extra install step is a barrier for the main audience. |
