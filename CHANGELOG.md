# Changelog

All notable changes are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and versions follow
[Semantic Versioning](https://semver.org/). Below 1.0, minor versions may change the API.

## Unreleased

### Added

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

- Spaces in query strings are sent as `%20`. httpx sends `+`, which this server reads
  literally, so `resolve("Viet Nam")` reached it as `Viet+Nam`.
