# Changelog

All notable changes are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and versions follow
[Semantic Versioning](https://semver.org/). Below 1.0, minor versions may change the API.

## [Unreleased]

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

[Unreleased]: https://github.com/nerd-factory/undata/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/nerd-factory/undata/releases/tag/v0.1.0
