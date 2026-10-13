"""The analyses UN reports run most often, one function each.

* :func:`progress` - is a country on track for an SDG target? The UN Statistics
  Division's published "trend to target" method, country by country.
* :func:`trend` - how fast a value has moved since a baseline year.
* :func:`gap` - the gap between two groups: women and men, rural and urban, poorest
  and richest.
* :func:`profile` - one country across many indicators, beside its region and the world.
* :func:`benchmark` - UN groups and regions against each other, using published totals.
* :func:`availability` - which countries report which indicators, and how recently.

Each returns a plain table that :func:`undata.chart`, :func:`undata.describe`,
:func:`undata.save` and :func:`undata.ai_pack` understand.
"""

from __future__ import annotations

import warnings
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from typing import Any, Final, Literal

import pandas as pd

from ._long import keep
from .breakdowns import slices_by
from .data import get, latest, totals
from .errors import MissingDataWarning, UNDataWarning
from .indicators import check
from .places import expand, m49, resolve

__all__ = [
    "STATUSES",
    "availability",
    "benchmark",
    "cagr",
    "gap",
    "profile",
    "progress",
    "trend",
]

Better = Literal["higher", "lower"]

#: The UN Statistics Division's method, as published.
PROGRESS_METHOD: Final = (
    "UN Statistics Division, The Sustainable Development Goals Report 2026: Technical Note "
    "for Progress Assessment"
)
PROGRESS_METHOD_URL: Final = (
    "https://unstats.un.org/sdgs/files/report/2026/Technical_Note_for_Progress_Assessment_2026.pdf"
)

ON_TRACK: Final = "On track or target met"
MODERATE: Final = "Moderate progress, but acceleration needed"
MARGINAL: Final = "Marginal progress, and significant acceleration needed"
STAGNATION: Final = "Stagnation"
REGRESSION: Final = "Regression"
INSUFFICIENT: Final = "Insufficient data"

#: Best first. The order charts and summaries use.
STATUSES: Final = (ON_TRACK, MODERATE, MARGINAL, STAGNATION, REGRESSION, INSUFFICIENT)


@dataclass(frozen=True)
class _Band:
    status: str
    low: float  # the band's bounds on the trend measure (ratio or growth rate)
    high: float
    score_low: float
    score_high: float


#: Bands on the ratio (projected 2030 change / required change), for series with a
#: 2030 target. The outer bounds are the note's operational limits, 1.5 and -0.5.
_RATIO_BANDS: Final = (
    _Band(ON_TRACK, 0.95, 1.5, 4, 5),
    _Band(MODERATE, 0.50, 0.95, 3, 4),
    _Band(MARGINAL, 0.10, 0.50, 2, 3),
    _Band(STAGNATION, 0.0, 0.10, 1, 2),
    _Band(REGRESSION, -0.5, 0.0, 0, 1),
)

#: Bands on the annual growth rate, for series without a 2030 target, where an increase
#: is desirable. Mirrored when a decrease is. Outer bounds are the note's 0.05 and -0.05.
_GROWTH_BANDS: Final = (
    _Band(ON_TRACK, 0.02, 0.05, 4, 5),
    _Band(MODERATE, 0.0125, 0.02, 3, 4),
    _Band(MARGINAL, 0.005, 0.0125, 2, 3),
    _Band(STAGNATION, 0.0, 0.005, 1, 2),
    _Band(REGRESSION, -0.05, 0.0, 0, 1),
)


def _carry(frame: pd.DataFrame, source: pd.DataFrame, **extra: Any) -> None:
    """Give ``frame`` the metadata of the table it was built from, plus ``extra``."""
    long = extra.pop("long", None)
    merged: dict[Any, Any] = {**source.attrs}
    merged.update(extra)
    frame.attrs = merged
    if long is not None:
        keep(frame, long)


def _baseline(points: pd.DataFrame, baseline: int) -> pd.Series | None:
    """The note's baseline rule: the baseline year if there is data, else the first later year."""
    later = points[points["year"] >= baseline].sort_values("year")
    return None if later.empty else later.iloc[0]


def cagr(start: float, end: float, years: int) -> float | None:
    """Compound annual growth rate, or ``None`` where it is undefined.

    Example:
        >>> round(cagr(100, 121, 2), 4)
        0.1
        >>> cagr(0, 5, 3) is None
        True
    """
    if years <= 0 or start <= 0 or end <= 0:
        return None
    return float((end / start) ** (1 / years) - 1)


def _score(value: float, bands: Sequence[_Band], *, mirrored: bool = False) -> tuple[str, float]:
    """The note's linear rescaling of a trend measure into a status and a 0-5 score."""
    measure = -value if mirrored else value
    for band in bands:
        if measure >= band.low or band is bands[-1]:
            clipped = min(max(measure, band.low), band.high)
            share = (clipped - band.low) / (band.high - band.low)
            return band.status, band.score_low + share * (band.score_high - band.score_low)
    raise AssertionError("unreachable: the last band catches everything")  # pragma: no cover


def _assess(
    base_year: int,
    base: float,
    last_year: int,
    last: float,
    *,
    better: Better,
    target: float | None,
    target_year: int,
) -> dict[str, Any]:
    """Assess one country's series by the UNSD method. Returns the computed columns."""
    out: dict[str, Any] = {"cagr_pct": None, "projected": None, "ratio": None, "note": ""}
    rate = cagr(base, last, last_year - base_year)
    if rate is not None:
        out["cagr_pct"] = rate * 100
    if last_year <= base_year:
        return {**out, "status": INSUFFICIENT, "score": None, "note": "only one year of data"}
    if target is not None:
        meets = last <= target if better == "lower" else last >= target
        met_at_base = base <= target if better == "lower" else base >= target
        if met_at_base:
            # The note sets this case by hand when the baseline equals the target: on
            # track while the latest value meets the target, regression otherwise.
            status = ON_TRACK if meets else REGRESSION
            note = "target already met at baseline" if meets else "met at baseline, no longer"
            return {**out, "status": status, "score": 5.0 if meets else 0.0, "note": note}
        if rate is None:
            return {**out, "status": INSUFFICIENT, "score": None, "note": "growth rate undefined"}
        projected = last * (1 + rate) ** (target_year - last_year)
        ratio = (projected - base) / (target - base)
        status, score = _score(ratio, _RATIO_BANDS)
        return {**out, "projected": projected, "ratio": ratio, "status": status, "score": score}
    if rate is None:
        return {**out, "status": INSUFFICIENT, "score": None, "note": "growth rate undefined"}
    status, score = _score(rate, _GROWTH_BANDS, mirrored=better == "lower")
    return {**out, "status": status, "score": score}


PROGRESS_COLUMNS: Final = [
    "country",
    "iso3",
    "status",
    "score",
    "baseline_year",
    "baseline_value",
    "latest_year",
    "latest_value",
    "cagr_pct",
    "projected",
    "target",
    "ratio",
    "note",
    "unit",
    "indicator_name",
    "indicator",
    "source",
]


def progress(
    indicator: str,
    countries: str | Iterable[str],
    *,
    better: Better,
    target: float | None = None,
    baseline: int = 2015,
    target_year: int = 2030,
) -> pd.DataFrame:
    """Assess each country's progress towards an SDG target, by the UN's own method.

    This applies the UN Statistics Division's "trend to target" method, from the
    Technical Note for Progress Assessment of The Sustainable Development Goals Report
    2026, to each country:

    * With a 2030 ``target``: the growth rate since the baseline is projected to 2030,
      and the projected change is compared with the change needed to reach the target.
    * Without one: the growth rate itself is compared with fixed thresholds.

    Each country gets one of five statuses, from "On track or target met" to
    "Regression", and a score from 0 to 5. Countries with fewer than two years of data
    since the baseline are marked "Insufficient data". The note does not cover a
    country already past the target at the baseline; undata applies the note's rule for
    a baseline equal to the target: on track while the latest value still meets it.

    Args:
        indicator: An indicator id, or an SDG number such as ``"3.1.1"``.
        countries: Countries, regions or groups, such as ``"LDCs"``.
        better: ``"lower"`` if a fall is progress (deaths, poverty), ``"higher"`` if a
            rise is (access, completion). Required: undata will not guess.
        target: The 2030 target value, such as 70 for maternal mortality (target 3.1).
            Leave out for indicators without a numerical target.
        baseline: The baseline year. The note uses 2015, or the first later year with data.
        target_year: The year the target is for.

    Returns:
        One row per country with its status, score, baseline and latest values, growth
        rate, and (with a target) the 2030 projection. ``.attrs["summary"]`` counts the
        countries per status, and ``.attrs["method"]`` cites the method.

    Example:
        >>> import undata as un
        >>> table = un.progress("3.1.1", "LDCs", target=70, better="lower")  # doctest: +SKIP
    """
    if better not in ("higher", "lower"):
        raise ValueError('better= must be "higher" or "lower".')
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", MissingDataWarning)
        series = get(indicator, countries, years=(baseline, date.today().year))
    places = expand(countries)
    rows: list[dict[str, Any]] = []
    for place in places:
        points = series[series["country"] == place.name].dropna(subset=["value"])
        row: dict[str, Any] = {"country": place.name, "iso3": place.iso3, "target": target}
        start = _baseline(points, baseline)
        if start is None:
            rows.append({**row, "status": INSUFFICIENT, "note": "no data since the baseline"})
            continue
        end = points.sort_values("year").iloc[-1]
        row.update(
            baseline_year=int(start["year"]),
            baseline_value=float(start["value"]),
            latest_year=int(end["year"]),
            latest_value=float(end["value"]),
            unit=end["unit"],
            indicator_name=end["indicator_name"],
            indicator=end["indicator"],
            source=end["source"],
        )
        row.update(
            _assess(
                row["baseline_year"],
                row["baseline_value"],
                row["latest_year"],
                row["latest_value"],
                better=better,
                target=target,
                target_year=target_year,
            )
        )
        rows.append(row)
    frame = pd.DataFrame(rows, columns=PROGRESS_COLUMNS)
    numbers = [
        "score",
        "baseline_value",
        "latest_value",
        "cagr_pct",
        "projected",
        "target",
        "ratio",
    ]
    frame[numbers] = frame[numbers].astype("float64")  # None -> NaN, so sums and charts work
    frame["status"] = pd.Categorical(frame["status"], categories=STATUSES, ordered=True)
    frame = frame.sort_values(["status", "score"], ascending=[True, False], ignore_index=True)
    for column in ("baseline_year", "latest_year"):
        frame[column] = frame[column].astype("Int64")
    _carry(
        frame,
        series,
        summary={s: int((frame["status"] == s).sum()) for s in STATUSES},
        method={"name": PROGRESS_METHOD, "url": PROGRESS_METHOD_URL},
        assessment={
            "better": better,
            "target": target,
            "baseline": baseline,
            "target_year": target_year,
        },
        long=series,
    )
    return frame


TREND_COLUMNS: Final = [
    "country",
    "iso3",
    "indicator_name",
    "start_year",
    "start_value",
    "end_year",
    "end_value",
    "change",
    "cagr_pct",
    "unit",
    "indicator",
    "source",
]


def trend(
    indicators: str | Sequence[str],
    countries: str | Iterable[str],
    *,
    since: int = 2015,
) -> pd.DataFrame:
    """How each country moved since a baseline year: the change and the annual growth rate.

    The start is ``since`` if there is data for it, otherwise the first later year (the
    UN's baseline rule); the end is the latest year with data.

    Args:
        indicators: One indicator id or SDG number, or a list.
        countries: Countries, regions or groups.
        since: The baseline year.

    Returns:
        One row per country and indicator: start and end years and values, the change,
        and ``cagr_pct``, the compound annual growth rate in percent.

    Example:
        >>> import undata as un
        >>> un.trend("undata/sdg/EG_ACS_ELEC", "Western Africa")  # doctest: +SKIP
    """
    series = get(indicators, countries, years=(since, date.today().year))
    rows: list[dict[str, Any]] = []
    for (_, _), points in series.groupby(["indicator", "country"], sort=False):
        ordered = points.dropna(subset=["value"]).sort_values("year")
        if len(ordered) < 2:  # noqa: PLR2004 — a trend needs two points
            continue
        first, last = ordered.iloc[0], ordered.iloc[-1]
        rate = cagr(
            float(first["value"]), float(last["value"]), int(last["year"]) - int(first["year"])
        )
        rows.append(
            {
                "country": last["country"],
                "iso3": last["iso3"],
                "indicator_name": last["indicator_name"],
                "start_year": int(first["year"]),
                "start_value": float(first["value"]),
                "end_year": int(last["year"]),
                "end_value": float(last["value"]),
                "change": float(last["value"]) - float(first["value"]),
                "cagr_pct": None if rate is None else rate * 100,
                "unit": last["unit"],
                "indicator": last["indicator"],
                "source": last["source"],
            }
        )
    frame = pd.DataFrame(rows, columns=TREND_COLUMNS)
    _carry(frame, series, long=series)
    return frame


#: The two groups compared by default, per breakdown.
DEFAULT_GROUPS: Final[Mapping[str, tuple[str, str]]] = {
    "sex": ("Female", "Male"),
    "urbanization": ("Rural", "Urban"),
    "location": ("Rural", "Urban"),
    "wealth quantile": ("Lowest quintile", "Highest quintile"),
}

#: The band within which a female/male ratio counts as parity (UNESCO's convention).
PARITY: Final = (0.97, 1.03)


def gap(
    indicator: str,
    countries: str | Iterable[str],
    *,
    by: str = "sex",
    groups: tuple[str, str] | None = None,
) -> pd.DataFrame:
    """The gap between two groups in each country: women and men, rural and urban.

    For each country, the latest year in which both groups have a value is used, so
    the two are always compared like with like.

    Args:
        indicator: An indicator id, or an SDG number, that has the breakdown.
        countries: Countries, regions or groups.
        by: The breakdown, such as ``"sex"``, ``"urbanization"`` or ``"wealth quantile"``.
        groups: The two groups to compare, as the breakdown names them. Defaults to
            female and male, rural and urban, or poorest and richest quintile.

    Returns:
        One row per country: the year, each group's value, ``ratio`` (first group divided
        by the second: for sex, the parity index), ``difference``, and for sex,
        ``parity`` (true when the ratio is within 0.97 to 1.03).

    Example:
        >>> import undata as un
        >>> completion = "undata/sdg/SE_TOT_CPLR.EDUCATION_LEVEL--ISCED11_1"
        >>> un.gap(completion, "Western Africa")  # doctest: +SKIP
    """
    column = by.strip().lower()
    resolved = next(iter(check(indicator)))
    labels = sorted(set(slices_by(resolved, by).values()))
    wanted = groups or DEFAULT_GROUPS.get(column)
    chosen = tuple(_match(want, labels) for want in wanted) if wanted else ()
    if len(chosen) != 2 or None in chosen:  # noqa: PLR2004
        raise ValueError(
            f"Choose two of the groups {resolved} has by {by}: {', '.join(labels)}. "
            'Pass them as groups=("A", "B").'
        )
    first, second = str(chosen[0]), str(chosen[1])
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", MissingDataWarning)
        table = get(resolved, countries, by=by)
    rows: list[dict[str, Any]] = []
    missing: list[dict[str, str]] = []
    for place in expand(countries):
        mine = table[table["country"] == place.name]
        a = mine[mine[column] == first].set_index("year")["value"]
        b = mine[mine[column] == second].set_index("year")["value"]
        both = sorted(set(a.dropna().index) & set(b.dropna().index))
        if not both:
            missing.append({"country": place.name, "indicator_name": resolved})
            continue
        year = both[-1]
        va, vb = float(a[year]), float(b[year])
        row = mine.iloc[0]
        result: dict[str, Any] = {
            "country": place.name,
            "iso3": place.iso3,
            "year": int(year),
            first: va,
            second: vb,
            "ratio": va / vb if vb else None,
            "difference": va - vb,
            "unit": row["unit"],
            "indicator": resolved,
            "source": row["source"],
        }
        if column == "sex" and result["ratio"] is not None:
            result["parity"] = PARITY[0] <= result["ratio"] <= PARITY[1]
        rows.append(result)
    if missing:
        names = ", ".join(m["country"] for m in missing[:8])
        more = f" and {len(missing) - 8} more" if len(missing) > 8 else ""  # noqa: PLR2004
        warnings.warn(
            f"No year with both {first} and {second} for {len(missing)} places: {names}{more}.",
            MissingDataWarning,
            stacklevel=2,
        )
    frame = pd.DataFrame(rows)
    if not frame.empty:
        frame["ratio"] = frame["ratio"].astype("float64")
    _carry(
        frame,
        table,
        missing=missing,
        gap={"by": column, "groups": (first, second)},
        long=table,
    )
    return frame


def _match(wanted: str, labels: Sequence[str]) -> str | None:
    """The label equal to ``wanted``, or the only one that starts with it."""
    if wanted in labels:
        return wanted
    starts = [label for label in labels if label.lower().startswith(wanted.lower())]
    return starts[0] if len(starts) == 1 else None


def _region_of(iso3: str) -> str:
    """The narrowest M49 region a country sits in, by name."""
    country = next(c for c in m49() if c.iso3 == iso3)
    return country.intermediate_region or country.sub_region


PROFILE_COLUMNS: Final = [
    "indicator_name",
    "value",
    "year",
    "region",
    "region_value",
    "world_value",
    "rank",
    "out_of",
    "cagr_pct",
    "unit",
    "indicator",
    "source",
]


def profile(country: str, indicators: Sequence[str], *, since: int = 2015) -> pd.DataFrame:
    """One country across many indicators, beside its region and the world.

    For each indicator: the country's latest value and year, the published figure for
    its M49 region and for the world (when the platform holds one), its rank among the
    countries of its region (1 is the highest value), and its growth rate since
    ``since``.

    Args:
        country: The country.
        indicators: Indicator ids or SDG numbers.
        since: The baseline year for the growth rate.

    Returns:
        One row per indicator.

    Example:
        >>> import undata as un
        >>> un.profile("Chad", ["undata/sdg/EG_ACS_ELEC", "3.1.1"])  # doctest: +SKIP
    """
    place = resolve(country)
    if place.kind != "country" or place.iso3 is None:
        raise ValueError(f"{place.name} is not a country. un.profile() describes one country.")
    region_name = _region_of(place.iso3)
    names = check(list(indicators))
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UNDataWarning)
        peers = latest(list(names), region_name)
        published = totals(list(names), [region_name, "World"], latest=True)
        moved = trend(list(names), place.name, since=since)
    rows: list[dict[str, Any]] = []
    for indicator, name in names.items():
        mine = peers[(peers["indicator"] == indicator)]
        own = mine[mine["country"] == place.name]
        ranked = mine.sort_values("value", ascending=False).reset_index(drop=True)
        position = ranked.index[ranked["country"] == place.name]
        pub = published[published["indicator"] == indicator].set_index("country")["value"]
        moved_row = moved[moved["indicator"] == indicator]
        rows.append(
            {
                "indicator_name": name,
                "value": float(own["value"].iloc[0]) if len(own) else None,
                "year": int(own["year"].iloc[0]) if len(own) else None,
                "region": region_name,
                "region_value": float(pub[region_name]) if region_name in pub else None,
                "world_value": float(pub["World"]) if "World" in pub else None,
                "rank": int(position[0]) + 1 if len(position) else None,
                "out_of": len(ranked),
                "cagr_pct": moved_row["cagr_pct"].iloc[0] if len(moved_row) else None,
                "unit": own["unit"].iloc[0] if len(own) else None,
                "indicator": indicator,
                "source": own["source"].iloc[0] if len(own) else None,
            }
        )
    frame = pd.DataFrame(rows, columns=PROFILE_COLUMNS)
    frame["year"] = frame["year"].astype("Int64")
    frame["rank"] = frame["rank"].astype("Int64")
    _carry(frame, peers, country=place.name, profile={"country": place.name, "region": region_name})
    return keep(frame, peers[peers["country"] == place.name].reset_index(drop=True))


def benchmark(
    indicator: str,
    places: Sequence[str] = ("World", "LDCs", "LLDCs", "SIDS"),
    *,
    baseline: int = 2015,
) -> pd.DataFrame:
    """Compare regions and UN groups using the totals the agency published for them.

    Args:
        indicator: An indicator id or SDG number.
        places: Regions or groups. Defaults to the world and the three UN groups.
        baseline: The baseline year (or the first later year with data).

    Returns:
        One row per place: baseline and latest values and years, the change and the
        annual growth rate. Places without a published total are named in a warning.

    Example:
        >>> import undata as un
        >>> un.benchmark("3.1.1")  # doctest: +SKIP
    """
    series = totals(indicator, list(places), years=(baseline, date.today().year))
    rows: list[dict[str, Any]] = []
    for name, points in series.groupby("country", sort=False):
        ordered = points.dropna(subset=["value"]).sort_values("year")
        start, end = ordered.iloc[0], ordered.iloc[-1]
        rate = cagr(
            float(start["value"]), float(end["value"]), int(end["year"]) - int(start["year"])
        )
        rows.append(
            {
                "place": name,
                "baseline_year": int(start["year"]),
                "baseline_value": float(start["value"]),
                "latest_year": int(end["year"]),
                "latest_value": float(end["value"]),
                "change": float(end["value"]) - float(start["value"]),
                "cagr_pct": None if rate is None else rate * 100,
                "unit": end["unit"],
                "indicator_name": end["indicator_name"],
                "source": end["source"],
            }
        )
    frame = pd.DataFrame(rows)
    _carry(frame, series, long=series)
    return frame


def availability(
    indicators: Sequence[str],
    countries: str | Iterable[str],
    *,
    within: int | None = None,
) -> pd.DataFrame:
    """Which countries report which indicators, and how recently.

    Args:
        indicators: Indicator ids or SDG numbers.
        countries: Countries, regions or groups.
        within: Count only values from the past this many years as available.

    Returns:
        A grid with countries down the side and indicators across the top, holding the
        year of each country's latest value, blank where there is none. ``.attrs``
        holds the share of countries reporting each indicator.

    Example:
        >>> import undata as un
        >>> un.availability(["3.1.1", "undata/sdg/EG_ACS_ELEC"], "SIDS")  # doctest: +SKIP
    """
    names = check(list(indicators))
    places = expand(countries)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UNDataWarning)
        found = latest(list(names), countries, within=within)
    grid = found.pivot_table(
        index="country", columns="indicator_name", values="year", aggfunc="max"
    )
    grid = grid.reindex(index=[p.name for p in places], columns=list(names.values()))
    grid = grid.astype("Int64")
    grid.index.name = "country"
    grid.columns.name = None
    reporting = {name: int(grid[name].notna().sum()) for name in grid.columns}
    _carry(
        grid,
        found,
        availability={"countries": len(places), "reporting": reporting},
        long=found,
    )
    return grid


# ── Sentences ────────────────────────────────────────────────────────────


def _fmt(value: float) -> str:
    from .summary import fmt_number  # noqa: PLC0415 — summary imports this module lazily too

    return fmt_number(value)


def _plain(label: str) -> str:
    """'Rural area (degree of urbanization)' -> 'rural area'."""
    return label.split(" (", maxsplit=1)[0].lower()


def _listed(names: Sequence[str], limit: int = 5) -> str:
    shown = sorted(names)
    return ", ".join(shown) if len(shown) <= limit else ""


def describe_analysis(table: pd.DataFrame) -> str | None:
    """The sentence for a progress, gap or profile table, or ``None`` for other tables."""
    attrs = table.attrs
    if "assessment" in attrs and "status" in table.columns:
        return _describe_progress(table)
    if "gap" in attrs and "ratio" in table.columns:
        return _describe_gap(table)
    if "profile" in attrs and "rank" in table.columns:
        return _describe_profile(table)
    return None


def _describe_progress(table: pd.DataFrame) -> str:
    assessment = table.attrs["assessment"]
    named = table["indicator_name"].dropna()
    name = str(named.iloc[0]).split(" [", maxsplit=1)[0] if len(named) else "The indicator"
    target = assessment.get("target")
    since = f"since {assessment.get('baseline', 2015)} (or the first year after)"
    if target is not None:
        how = (
            f"trend {since} is projected to {assessment.get('target_year', 2030)} and "
            f"compared with the target of {_fmt(float(target))}"
        )
    else:
        how = f"yearly rate of change {since} is scored, as no target was given"
    parts = []
    for status in STATUSES:
        who = table.loc[table["status"] == status, "country"].astype(str).tolist()
        if who:
            listed = _listed(who)
            parts.append(
                f"{len(who)} {status[0].lower() + status[1:]}" + (f" ({listed})" if listed else "")
            )
    return (
        f"{name}, {len(table)} countries. Each country's {how}. {'; '.join(parts)}. "
        f"Method: {PROGRESS_METHOD}."
    )


def _describe_gap(table: pd.DataFrame) -> str:
    first, second = table.attrs["gap"]["groups"]
    a, b = _plain(str(first)), _plain(str(second))
    rows = table.dropna(subset=["ratio"]).sort_values("ratio")
    if rows.empty:
        return f"No country has {a} and {b} values for the same year."
    unit = str(rows["unit"].iloc[0])
    pct = "%" if unit.startswith("%") or unit.lower().startswith("percent") else ""
    widest = (
        rows.iloc[0]
        if abs(1 - rows["ratio"].iloc[0]) >= abs(1 - rows["ratio"].iloc[-1])
        else rows.iloc[-1]
    )
    close = rows[(rows["ratio"] >= PARITY[0]) & (rows["ratio"] <= PARITY[1])]["country"].tolist()
    sentence = (
        f"Comparing {a} with {b} in the latest year with both: the widest gap is in "
        f"{widest['country']}, {_fmt(float(widest[first]))}{pct} against "
        f"{_fmt(float(widest[second]))}{pct} in {int(widest['year'])} (a ratio of "
        f"{float(widest['ratio']):.2f})."
    )
    if close:
        sentence += (
            f" {len(close)} of {len(rows)} countries are within {PARITY[0]}-{PARITY[1]} of parity: "
            f"{', '.join(sorted(close))}."
        )
    else:
        sentence += f" No country is within {PARITY[0]}-{PARITY[1]} of parity."
    return sentence


def ordinal(rank: int, out_of: int) -> str:
    """'highest of 9', '3rd highest of 9' or 'lowest of 9': reads the same for good and bad."""
    if rank == out_of and out_of > 1:
        return f"lowest of {out_of}"
    if rank == 1:
        return f"highest of {out_of}"
    teen = 10 <= rank % 100 <= 20  # noqa: PLR2004
    suffix = "th" if teen else {1: "st", 2: "nd", 3: "rd"}.get(rank % 10, "th")
    return f"{rank}{suffix} highest of {out_of}"


def _describe_profile(table: pd.DataFrame) -> str:
    country, region = table.attrs["profile"]["country"], table.attrs["profile"]["region"]
    lines = [f"{country}, latest values beside {region} and the world:"]
    for _, row in table.iterrows():
        if pd.isna(row["value"]):
            lines.append(f"  {str(row['indicator_name']).split(' [')[0]}: no data.")
            continue
        bits = [f"{_fmt(float(row['value']))} ({int(row['year'])})"]
        if pd.notna(row["rank"]):
            bits.append(f"{ordinal(int(row['rank']), int(row['out_of']))} in {region}")
        if pd.notna(row["world_value"]):
            bits.append(f"world {_fmt(float(row['world_value']))}")
        lines.append(f"  {str(row['indicator_name']).split(' [')[0]}: {'; '.join(bits)}.")
    return "\n".join(lines)
