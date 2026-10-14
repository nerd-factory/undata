# Contributing

Short version: turn up, be curious, break something interesting.

There is no application process and no minimum qualification. If you have never used
GitHub before, start at [Nerd Lab Discussions](https://github.com/nerd-factory/nerd-lab/discussions)
and ask the question you are worried is too basic. It is not.

Things that are real contributions:

- "I followed the README and it did not work."
- "This error message did not tell me what to do."
- "The platform returned something this package did not expect" — with the URL.
- A typo. Yes, that one counts too.

## Setting up

You need [uv](https://docs.astral.sh/uv/). It installs the right Python for you.

```bash
git clone https://github.com/nerd-factory/undata && cd undata
uv sync
uv run pytest
```

## Before you open a pull request

```bash
uv run ruff format .
uv run ruff check .
uv run mypy
uv run pytest
```

CI runs the same four on Linux, macOS and Windows, on every supported Python.

## What we care about in review

- **Safe by default.** The package never substitutes, rounds away or zero-fills anything
  without saying so. If a change makes a wrong answer easier to get, it needs a very good
  reason.
- **Errors say what to do next.** A message that only restates the HTTP status is a bug.
- **Tests that pin behaviour, not implementation.** Unit tests mock HTTP with `respx`.
  Anything that depends on how the live platform behaves also gets a test in
  `tests/live/`, so the nightly run notices when the platform changes.
- **Typed and documented.** Every public function has type hints and a docstring with a
  runnable example; doctests run as part of the suite.
- **Written for someone new to data.** Function names are plain verbs, arguments accept
  names rather than codes, results are tables, and every warning or error says what to
  do next in plain English.
- **No dependency arrives without a reason attached.** The core needs httpx, pandas and
  openpyxl, and nothing else.
- **Does it sound like us?** Dry, exact, unhurried. No hype.

## Layout

```
src/undata/data.py         get(), latest(), totals(), change(), compare(), wide()
src/undata/places.py       countries, regions and groups, from the UN M49 list
src/undata/m49.csv         the UN M49 list itself; refresh with scripts/update_m49.py
src/undata/indicators.py   search() and about()
src/undata/sdg.py          the SDG tree, goal to fetchable series
src/undata/ask.py          what data.un.org's search box decided
src/undata/export.py       save(), cite(), for_ai(), powerquery()
src/undata/breakdowns.py   breakdowns() and get(by=...)
src/undata/summary.py      describe(): sentences from the numbers
src/undata/analysis.py     progress(), profile(), gap(), trend(), benchmark(), availability()
src/undata/chart.py        chart(): the chart catalogue (optional matplotlib)
src/undata/_interactive.py chart(interactive=True), with Plotly
src/undata/style.py        style() and the checked palettes
src/undata/tiles.csv       the tile-map grid; rebuild with scripts/build_tile_grid.py
src/undata/cli.py          the undata command
src/undata/mcp_server.py   the undata-mcp connector: one read-only MCP tool per function
src/undata/_http.py        the only module that touches the network
src/undata/_endpoints.py   one thin wrapper per API route, no interpretation
src/undata/dcid.py         the identifier grammar
src/undata/errors.py       every exception, each with a message that helps
tests/                     offline tests; tests/live/ calls the real API
examples/                  runnable use cases, run nightly against the live API
site/                      the use-cases page: template, build.py, charts.py
docs/                      the API reference (Sphinx), built from the docstrings
```

## The use-cases page

`site/public/index.html` is generated from `site/template.html` and the scripts in
`examples/`, and committed. After changing either, rebuild it (this runs every example
against the live API):

```bash
uv run python site/build.py
```

Pushing the result to `main` deploys it to https://nerd-factory.github.io/undata/.

## The API reference

`docs/` holds the reference pages; the content is the docstrings, so documenting a
function means writing its docstring (Google style: `Args:`, `Returns:`, `Example:`).
Build it locally with:

```bash
uv run --group docs sphinx-build -W docs _build/reference   # open _build/reference/index.html
```

CI builds it with warnings as errors, and the Pages workflow publishes it at
https://nerd-factory.github.io/undata/reference/ on every push to `main`. The connector's
tool list and the command-line help are generated from the code during the build.

## Releasing (maintainers)

Tag `vX.Y.Z` on `main` and push the tag. The release workflow builds, publishes to PyPI
through trusted publishing (no tokens anywhere), and creates the GitHub release. The `pypi`
environment requires a maintainer's approval before the upload step runs.

## One rule

Read the [Code of Conduct](CODE_OF_CONDUCT.md). It is short and it is enforced.
