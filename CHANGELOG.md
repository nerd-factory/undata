# Changelog

All notable changes are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and versions follow
[Semantic Versioning](https://semver.org/). Below 1.0, minor versions may change the API.

## [Unreleased]

## [0.2.0] - 2026-10-13

Everything a UN colleague was doing by hand in the 0.1 use cases, built in, on the UN's
own country list.

### Added

- undata's own country list: the UN M49 standard, shipped as `m49.csv` and refreshed by
  `scripts/update_m49.py`. Countries carry their official UN names; regions and
  sub-regions follow M49; LDCs, LLDCs and SIDS are the UN's current lists (44, 32, 53),
  where the platform's copies were out of date (46 and 47). Developed and developing
  countries are groups too. Places needs no request to the platform any more.
- Places outside M49 (such as Taiwan and Kosovo, which the platform holds) are in no
  list, region or group, and are reachable only by platform code, under the platform's
  name. M49 codes (`"704"`) work as input.
- `un.latest(..., within=10)`: each country's latest value from the past ten years, with
  the window recorded on the table and older values named.
- `un.coverage(table)`: who has a value, who was too old, who has none, and which years.
  It also goes into the Excel file as a `coverage` sheet.
- `un.ai_pack()`: data, metadata and a prompt, to upload to an AI assistant.
- `un.for_ai(task=..., question=...)`: tasks for the assistant (explain, brief, trends,
  gaps, chart). Markdown tables no longer need the tabulate package.

- UN development groupings as places: `"LDCs"`, `"LLDCs"`, `"SIDS"` (and their full names).
- `un.totals()`: the official figure for a region or group, as the agency published it.
  undata never computes a regional figure of its own.
- SDG indicator numbers such as `"3.1.1"` work wherever an indicator id does, when one
  series reports the indicator; otherwise `AmbiguousIndicatorError` lists the series.
- `wide=True` on `get`, `latest` and `totals`, and `un.wide()`: one column per indicator.
  Citations and saving still find the sources.
- `un.latest(..., since=YEAR)` leaves out older values and names them in a
  `StaleDataWarning`.
- `un.change()`: two years side by side, with the difference and the percentage change.
- `un.compare()`: indicators side by side, with a `CoverageWarning` saying who has what.
- `un.breakdowns()` and `un.get(..., by="sex")`: breakdowns by sex, age, wealth and more.
- `un.describe()`: plain-English sentences about a table, from fixed rules, not a model.
- `un.chart()`: ranked bars, lines or a dumbbell, chosen from the table, with the source
  underneath. Optional: `pip install "undata[charts]"`.
- `un.for_ai()`: a table with instructions, sources and gaps, for an AI assistant.
- `un.powerquery()`: Power Query (M) code for Power BI and Excel.
- `un.about()` gives the SDG indicator number and the UN Stats metadata document.
- `un.search()` shows one row per indicator with a count of its breakdowns, and how many
  places and years have data.
- A disk cache: `un.configure(cache=True)` and `un.clear_cache()`.
- An `undata` command for the terminal, with the same functions.

### Fixed

- On Windows, a cache with a zero lifetime could serve a response it had just written.
- The 403 message and the live tests now name all three country codes the firewall
  refuses on GET: ESH, GRC and SVN.
- A failure deep in paging through a very large answer now says what happened and how to
  narrow the request, instead of a bare HTTP 500.
- Requests for many places run several at a time.
- The shared connection is closed when Python exits.

### Changed

- The examples are now nine use cases written from real kinds of UN requests (a
  country briefing, SDG progress, women in parliament, refugees, conflict and homicide,
  disagreeing sources, an Excel data pack, a self-refreshing dashboard, checking the
  search box). Each ends with a sentence for the report, computed from the data.
- The use-cases page leads with them, with charts drawn from the same live data.
- The README's fallback logo is the ink version, which shows on PyPI's white page.

## [0.1.0] - 2026-10-13

First release.

### Added

- The friendly API, for people who need numbers rather than an API:
  `un.search`, `un.about`, `un.get`, `un.latest`, `un.countries`, `un.regions`,
  `un.sdg.goals/targets/indicators/series`, `un.ask`, `un.save` and `un.cite`. Tables
  have the same columns every time, with unit and source on every row.
- Places by name: UN names, everyday names, ISO codes and regions all work, and tables
  use UN M49 short names. Unknown names raise `PlaceNotFoundError` with suggestions;
  names inside several countries raise `AmbiguousPlaceError`. Nothing is substituted.
- Plain-English warnings: `MissingDataWarning` names countries with no data (never
  zero-filled), `MixedYearsWarning` flags "latest" values from different years, and
  `PlaceGuessedWarning` flags a place data.un.org's search box chose itself, read from
  its own `placeSource` field.
- `un.save` writes Excel with `data`, `sources` and `no data` sheets, or CSV.
- Search re-ranks results so names containing all your words come first, and hides
  series Data Commons imported from elsewhere unless `all_sources=True`.
- Ten examples rewritten on the friendly API, and the examples page rebuilt for
  colleagues new to data work.

- Transport layer: single-line JSON bodies, GET-only observations, percent-encoded
  relation expressions, retries on 429/502/503/504 honouring `Retry-After`, and
  `BlockedRequestError`, which explains a 403 instead of implying an API key exists.
- One wrapper per API route, including graph walks that follow `nextToken` past the
  500-value page cap.
- The dcid grammar: `parse_dcid`, `build_dcid`, `describe_dcid`, `child_countries_of`.
- A live contract suite that pins the platform behaviours the package depends on,
  including that variable search ranks Data Commons' older `sdg/...` copy above the
  UN's own `undata/sdg/...` series.

### Fixed

- A request mentioning Western Sahara (`ESH`) is refused by the firewall on GET, which
  made any request for Africa fail. Data is now fetched by POST, which it accepts.
- The 403 message named only the POST triggers; it now lists all three.
- The platform's "Latin America" region contains no countries, so it is no longer
  offered; "Latin America and the Caribbean" is suggested instead.

- Spaces in query strings are sent as `%20`. httpx sends `+`, which this server reads
  literally, so `resolve("Viet Nam")` reached it as `Viet+Nam`.

[Unreleased]: https://github.com/nerd-factory/undata/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/nerd-factory/undata/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/nerd-factory/undata/releases/tag/v0.1.0
