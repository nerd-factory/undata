"""Plain-English sentences about a table, worked out from its numbers.

:func:`describe` writes the kind of sentence that goes under a chart or into a
briefing: the highest and the lowest, how many fell or rose, which years the values
come from. It uses fixed rules, not a language model, so the same table always gives
the same words, and every number in them is in the table.
"""

from __future__ import annotations

import pandas as pd

from ._long import long_of

__all__ = ["coverage", "describe", "fmt_number"]

_MAX_COUNTRIES = 8


def fmt_number(value: float) -> str:
    """A number at a sensible precision: 1,234 · 123 · 12.3 · 1.23."""
    size = abs(value)
    if size >= 100:  # noqa: PLR2004
        return f"{value:,.0f}"
    if size >= 10:  # noqa: PLR2004
        return f"{value:.1f}"
    return f"{value:.2f}"


def _is_percent(unit: object) -> bool:
    return isinstance(unit, str) and unit.strip().lower() in {"percent", "%"}


def _value(value: float, unit: object) -> str:
    """A number, with % attached when the unit is a percentage. Other units go in the heading."""
    return f"{fmt_number(value)}%" if _is_percent(unit) else fmt_number(value)


def _heading(name: str, group: pd.DataFrame) -> str:
    units = group["unit"].dropna() if "unit" in group else pd.Series(dtype=str)
    unit = str(units.iloc[0]) if len(units) else ""
    return name if not unit or _is_percent(unit) else f"{name} ({unit.lower()})"


def _years(group: pd.DataFrame) -> str:
    first, last = int(group["year"].min()), int(group["year"].max())
    return f"in {first}" if first == last else f"from {first} to {last}"


def _latest_like(group: pd.DataFrame, name: str) -> str:
    group = group.dropna(subset=["value"]).sort_values("value", ascending=False)
    top, bottom = group.iloc[0], group.iloc[-1]
    unit = top["unit"]
    if len(group) == 1:
        return f"{name}: {top['country']}, {_value(top['value'], unit)} ({top['year']})."
    median = group["value"].median()
    return (
        f"{name}: highest in {top['country']} ({_value(top['value'], unit)}, {top['year']}) "
        f"and lowest in {bottom['country']} ({_value(bottom['value'], unit)}, "
        f"{bottom['year']}); the median across {len(group)} places is "
        f"{_value(median, unit)}. Values are {_years(group)}."
    )


def _series(group: pd.DataFrame, name: str) -> str:
    lines = [f"{name}:"]
    countries = list(dict.fromkeys(group["country"]))
    for country in countries[:_MAX_COUNTRIES]:
        rows = group[group["country"] == country].dropna(subset=["value"]).sort_values("year")
        first, last = rows.iloc[0], rows.iloc[-1]
        unit = last["unit"]
        if first["year"] == last["year"]:
            lines.append(f"  {country}: {_value(last['value'], unit)} in {last['year']}.")
            continue
        pct = (last["value"] / first["value"] - 1) * 100 if first["value"] else None
        direction = "rose" if last["value"] > first["value"] else "fell"
        if last["value"] == first["value"]:
            direction = "was unchanged"
        pct_text = f" ({pct:+.0f}%)" if pct is not None and direction != "was unchanged" else ""
        lines.append(
            f"  {country} {direction} from {_value(first['value'], unit)} in {first['year']} "
            f"to {_value(last['value'], unit)} in {last['year']}{pct_text}."
        )
    if len(countries) > _MAX_COUNTRIES:
        lines.append(f"  ...and {len(countries) - _MAX_COUNTRIES} more places.")
    return "\n".join(lines)


def _change(group: pd.DataFrame, name: str) -> str:
    start, end = int(group["start_year"].iloc[0]), int(group["end_year"].iloc[0])
    fell = group[group["change"] < 0]
    rose = group[group["change"] > 0]
    total = len(group)
    if len(fell) == total:
        moved = f"fell in all {total} places"
    elif len(rose) == total:
        moved = f"rose in all {total} places"
    else:
        moved = f"fell in {len(fell)} and rose in {len(rose)} of {total} places"
    text = f"{name}: between {start} and {end} it {moved}."
    biggest = group.dropna(subset=["change_pct"])
    if not biggest.empty:
        ordered = biggest.sort_values("change_pct")
        low, high = ordered.iloc[0], ordered.iloc[-1]
        if low["change_pct"] < 0:
            text += f" The largest fall was in {low['country']} ({low['change_pct']:+.0f}%)."
        if high["change_pct"] > 0:
            text += f" The largest rise was in {high['country']} ({high['change_pct']:+.0f}%)."
    return text


def describe(table: pd.DataFrame) -> str:
    """Write plain-English sentences about a table from :mod:`undata`.

    For a table of latest values or totals: the highest, the lowest and the median,
    with the years they come from. For several years: how each country moved from
    its first year to its last. For :func:`undata.change`: how many fell or rose,
    and the largest moves. Countries with no data are mentioned, not counted as zero.

    Args:
        table: A table from :func:`undata.get`, :func:`undata.latest`,
            :func:`undata.totals`, :func:`undata.change` or :func:`undata.wide`, or
            from :func:`undata.progress`, :func:`undata.gap` or :func:`undata.profile`,
            which get their own summary: statuses, the widest gap, or ranks.

    Returns:
        A paragraph per indicator, ready to paste and edit.

    Example:
        >>> import undata as un
        >>> table = un.latest("undata/sdg/EG_ACS_ELEC", "Southern Asia")
        >>> print(un.describe(table))  # doctest: +SKIP
    """
    from .analysis import describe_analysis  # noqa: PLC0415 — analysis builds on summary's helpers

    sentence = describe_analysis(table)
    if sentence is not None:
        return sentence
    if "change_pct" in table.columns:
        source, kind = table, "change"
    else:
        source = long_of(table)
        if not {"country", "year", "value", "indicator_name"} <= set(source.columns):
            raise ValueError(
                "describe() works on tables from un.get(), un.latest(), un.totals(), "
                "un.change() or un.wide()."
            )
        several = source.groupby(["country", "indicator_name"])["year"].nunique().max()
        kind = "series" if several and several > 1 else "latest"
    if source.empty:
        return "The table is empty: none of the places asked for has data."
    paragraphs = []
    for name, group in source.groupby("indicator_name", sort=False):
        heading = _heading(str(name), group)
        if kind == "change":
            paragraphs.append(_change(group, heading))
        elif kind == "series":
            paragraphs.append(_series(group, heading))
        else:
            paragraphs.append(_latest_like(group, heading))
    window = table.attrs.get("window") or {}
    stale = table.attrs.get("stale") or []
    if window.get("since") is not None:
        span = (
            f"the last {window['within_years']} years"
            if window.get("within_years") is not None
            else f"{window['since']} or later"
        )
        text = f"Only each place's latest value from {span} is used"
        if stale:
            old = sorted({s["country"] for s in stale})
            text += f"; {len(old)} places had nothing that recent ({_listing(old)})"
        paragraphs.append(text + ".")
    missing = table.attrs.get("missing") or []
    if missing:
        names = sorted({m["country"] for m in missing})
        paragraphs.append(f"No data for {_listing(names)}; they are not counted as zero.")
    return "\n\n".join(paragraphs)


def _listing(names: list[str]) -> str:
    shown = ", ".join(names[:_MAX_COUNTRIES])
    more = len(names) - _MAX_COUNTRIES
    return f"{shown} and {more} more" if more > 0 else shown


COVERAGE_COLUMNS = [
    "indicator_name",
    "asked",
    "with_value",
    "too_old",
    "no_data",
    "oldest_year",
    "newest_year",
    "median_year",
    "window",
]


def _window_text(window: dict[str, object] | None) -> str:
    if not window or window.get("since") is None:
        return "any year"
    within = window.get("within_years")
    since, until = window["since"], window.get("until")
    return f"{since}-{until} (last {within} years)" if within is not None else f"{since} on"


def coverage(table: pd.DataFrame) -> pd.DataFrame:
    """Say how complete a table is: who has a value, who was too old, who has none.

    Args:
        table: A table from :func:`undata.latest` (with or without ``within=``),
            :func:`undata.get`, :func:`undata.totals` or :func:`undata.wide`.

    Returns:
        One row per indicator: how many places were asked for, how many have a value,
        how many had only values older than the window, how many have none at all,
        the oldest, newest and median year of the values kept, and the window.

    Example:
        >>> import undata as un
        >>> table = un.latest("3.1.1", "LDCs", within=5)  # doctest: +SKIP
        >>> un.coverage(table)  # doctest: +SKIP
    """
    source = long_of(table)
    asked_names = table.attrs.get("asked")
    missing = table.attrs.get("missing") or []
    stale = table.attrs.get("stale") or []
    window = _window_text(table.attrs.get("window"))
    names = list(
        dict.fromkeys(
            list(source["indicator_name"])
            + [m["indicator_name"] for m in missing]
            + [s["indicator_name"] for s in stale]
        )
    )
    rows = []
    for name in names:
        kept = source[source["indicator_name"] == name]
        have = set(kept["country"])
        too_old = {s["country"] for s in stale if s["indicator_name"] == name}
        none = {m["country"] for m in missing if m["indicator_name"] == name}
        asked = len(asked_names) if asked_names else len(have | too_old | none)
        years = kept["year"].dropna()
        rows.append(
            {
                "indicator_name": name,
                "asked": asked,
                "with_value": len(have),
                "too_old": len(too_old),
                "no_data": len(none),
                "oldest_year": int(years.min()) if len(years) else None,
                "newest_year": int(years.max()) if len(years) else None,
                "median_year": int(years.median()) if len(years) else None,
                "window": window,
            }
        )
    frame = pd.DataFrame(rows, columns=COVERAGE_COLUMNS)
    for column in ("oldest_year", "newest_year", "median_year"):
        frame[column] = frame[column].astype("Int64")
    return frame
