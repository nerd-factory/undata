"""The ``undata`` command: UN data from a terminal, no Python needed.

Examples::

    undata search "maternal mortality"
    undata about 3.1.1
    undata get 3.1.1 "Southern Asia" --years 2015-2023 --to maternal-mortality.xlsx
    undata latest undata/sdg/EG_ACS_ELEC Chad Niger Mali --since 2020
    undata totals 3.1.1 World LDCs SIDS --latest
    undata change 3.1.1 "Southern Asia" --start 2015 --end 2023 --describe
    undata sdg 16.1
    undata powerquery 3.1.1 LDCs > query.m

Several indicators can be given at once, separated by commas.
"""

from __future__ import annotations

import argparse
import sys
import warnings
from collections.abc import Sequence

import pandas as pd

from . import sdg
from ._session import clear_cache
from ._version import __version__
from .data import change, get, latest, totals
from .errors import UNDataError
from .export import powerquery, save
from .indicators import about, search
from .places import countries, regions
from .summary import coverage, describe


def _years(text: str | None) -> int | tuple[int, int] | None:
    if not text:
        return None
    if "-" in text:
        first, last = text.split("-", 1)
        return int(first), int(last)
    return int(text)


def _indicators(text: str) -> list[str]:
    return [part.strip() for part in text.split(",") if part.strip()]


def _show(table: pd.DataFrame, args: argparse.Namespace) -> None:
    if getattr(args, "to", None):
        path = save(table, args.to)
        print(f"Saved {len(table)} rows to {path}")
    else:
        keep_index = not isinstance(table.index, pd.RangeIndex)
        with pd.option_context("display.width", 200, "display.max_colwidth", 60):
            print(table.to_string(index=keep_index))
    if getattr(args, "describe", False):
        print()
        print(describe(table))


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="undata",
        description="UN data without the guessing: statistics from the UN System Data Commons.",
        epilog='Places can be country names, ISO codes, regions ("Southern Asia") or groups '
        "(LDCs, LLDCs, SIDS). Indicators can be ids or SDG numbers such as 3.1.1.",
    )
    parser.add_argument("--version", action="version", version=f"undata {__version__}")
    commands = parser.add_subparsers(dest="command", required=True, metavar="command")

    def data_command(name: str, help_text: str) -> argparse.ArgumentParser:
        cmd = commands.add_parser(name, help=help_text, description=help_text)
        cmd.add_argument("indicator", help="indicator id or SDG number; several with commas")
        cmd.add_argument("places", nargs="+", help="countries, regions or groups")
        cmd.add_argument("--to", metavar="FILE", help="save to .xlsx or .csv instead of printing")
        cmd.add_argument("--describe", action="store_true", help="add sentences for a report")
        return cmd

    cmd = commands.add_parser("search", help="find indicators by what they measure")
    cmd.add_argument("text")
    cmd.add_argument("--all-sources", action="store_true", help="include non-UN collections")
    cmd.add_argument("--breakdowns", action="store_true", help="list every breakdown")
    cmd.add_argument("--limit", type=int, default=20)

    cmd = commands.add_parser("about", help="what an indicator is and how much data exists")
    cmd.add_argument("indicator")

    cmd = data_command("get", "values for every year, or a range of years")
    cmd.add_argument("--years", help="a year (2020) or a range (2015-2023)")
    cmd.add_argument("--by", help="a breakdown, such as sex or age")
    cmd.add_argument("--wide", action="store_true", help="one column per indicator")

    cmd = data_command("latest", "each place's most recent value")
    cmd.add_argument("--within", type=int, help="latest value from the past N years only")
    cmd.add_argument("--since", type=int, help="leave out values older than this year")
    cmd.add_argument("--coverage", action="store_true", help="add who has data, and how old")
    cmd.add_argument("--wide", action="store_true", help="one column per indicator")

    cmd = data_command("totals", "the official figure for a region or group")
    cmd.add_argument("--years", help="a year (2020) or a range (2015-2023)")
    cmd.add_argument("--latest", action="store_true", help="only the most recent value")

    cmd = data_command("change", "the difference between two years")
    cmd.add_argument("--start", type=int, required=True)
    cmd.add_argument("--end", type=int, required=True)

    cmd = commands.add_parser("countries", help="list countries, all or in one region")
    cmd.add_argument("region", nargs="?")
    commands.add_parser("regions", help="list the regions and groups")

    cmd = commands.add_parser("sdg", help="walk the SDGs: goals, then 16, 16.1, 16.1.2")
    cmd.add_argument("number", nargs="?", help="a goal, target or indicator number")

    cmd = commands.add_parser("powerquery", help="Power Query (M) code for Power BI or Excel")
    cmd.add_argument("indicator")
    cmd.add_argument("places", nargs="+")
    cmd.add_argument("--years", help="a year (2020) or a range (2015-2023)")

    cmd = commands.add_parser("cache", help="manage the on-disk cache")
    cmd.add_argument("action", choices=["clear"])
    return parser


def _sdg_table(number: str) -> pd.DataFrame:
    """Goals with no number, then a goal's targets, a target's indicators, an indicator's series."""
    if not number:
        return sdg.goals()
    depth = number.count(".")
    if depth == 0:
        return sdg.targets(number)
    if depth == 1:
        return sdg.indicators(number)
    return sdg.series(number)


def _run(args: argparse.Namespace) -> None:
    command = args.command
    if command == "search":
        table = search(
            args.text, all_sources=args.all_sources, breakdowns=args.breakdowns, limit=args.limit
        )
        _show(table, args)
    elif command == "about":
        print(about(args.indicator))
    elif command == "get":
        _show(
            get(
                _indicators(args.indicator),
                args.places,
                _years(args.years),
                by=args.by,
                wide=args.wide,
            ),
            args,
        )
    elif command == "latest":
        table = latest(
            _indicators(args.indicator),
            args.places,
            within=args.within,
            since=args.since,
            wide=args.wide,
        )
        _show(table, args)
        if args.coverage:
            print()
            print(coverage(table).to_string(index=False))
    elif command == "totals":
        _show(
            totals(
                _indicators(args.indicator), args.places, _years(args.years), latest=args.latest
            ),
            args,
        )
    elif command == "change":
        _show(change(_indicators(args.indicator), args.places, args.start, args.end), args)
    elif command == "countries":
        _show(countries(args.region), args)
    elif command == "regions":
        _show(regions(), args)
    elif command == "sdg":
        _show(_sdg_table((args.number or "").strip()), args)
    elif command == "powerquery":
        print(powerquery(_indicators(args.indicator), args.places, _years(args.years)))
    elif command == "cache":
        print(f"Deleted {clear_cache()} cached responses.")


def main(argv: Sequence[str] | None = None) -> int:
    """Run the ``undata`` command. Returns the exit status.

    Warnings are collected and printed after the result, as plain notes rather than
    Python's file-and-line format, and errors as one line rather than a traceback.
    """
    args = _parser().parse_args(argv)
    status = 0
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        try:
            _run(args)
        except (UNDataError, ValueError, IndexError) as error:
            print(f"Error: {error}", file=sys.stderr)
            status = 1
    for warning in caught:
        if issubclass(warning.category, UserWarning):
            print(f"Note: {warning.message}", file=sys.stderr)
    return status


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
