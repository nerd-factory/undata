"""The 0.2 features, one block each, in the order of the roadmap."""

from __future__ import annotations

import warnings
from pathlib import Path

import httpx
import pandas as pd
import pytest
import respx

import undata as un
from undata import Transport, cli
from undata import _endpoints as ep
from undata.indicators import metadata_url

from .conftest import BASE
from .fake_api import ELEC, MMR, TOTN, FakeAPI

# ── 1. UN groupings ──────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "name", ["LDCs", "ldc", "Least developed countries", "least developed countries (LDCs)"]
)
def test_groupings_resolve(fake: FakeAPI, name: str) -> None:
    assert un.places.resolve(name).id == "undata-geo/G00404000"


def test_a_grouping_expands_to_its_members(fake: FakeAPI) -> None:
    assert [p.iso3 for p in un.places.expand("LDCs")] == ["BGD", "NPL", "COD"]
    assert {"Small Island Developing States (SIDS)"} <= set(un.regions()["region"])


# ── 2. Official totals ───────────────────────────────────────────────────


def test_totals_return_the_published_regional_figure(fake: FakeAPI) -> None:
    table = un.totals(MMR, ["World", "LDCs"], latest=True)

    assert list(table["country"]) == ["Least developed countries (LDCs)", "World"]
    assert list(table["value"]) == [313.1, 197.3]
    assert table["iso3"].isna().all()


def test_totals_keep_every_year_by_default_and_report_gaps(fake: FakeAPI) -> None:
    with pytest.warns(un.MissingDataWarning, match="Southern Asia"):
        table = un.totals(MMR, ["World", "Southern Asia"])

    assert list(table["year"]) == [2015, 2023]


# ── 3. SDG numbers as indicators ─────────────────────────────────────────


def test_an_sdg_number_with_one_series_is_used(fake: FakeAPI) -> None:
    table = un.get("3.1.1", "Bangladesh", years=2023)

    assert set(table["indicator"]) == {MMR}


def test_an_sdg_number_with_several_series_lists_them(fake: FakeAPI) -> None:
    with pytest.raises(un.AmbiguousIndicatorError, match="reported by 2 series") as caught:
        un.get("16.1.2", "Bangladesh")

    assert caught.value.suggestions == ["undata/sdg/VC_DTH_TOTN", "undata/sdg/VC_DTH_TOTR"]
    assert isinstance(caught.value, un.IndicatorNotFoundError)


def test_an_sdg_number_with_no_series_is_not_found(fake: FakeAPI) -> None:
    with pytest.raises(un.IndicatorNotFoundError):
        un.get("16.1.1", "Bangladesh")


# ── 4. Wide tables ───────────────────────────────────────────────────────


def test_wide_puts_indicators_across_and_keeps_the_sources(fake: FakeAPI) -> None:
    with pytest.warns(un.MixedYearsWarning):
        table = un.latest([ELEC, MMR], ["Bangladesh", "Nepal"], wide=True)

    assert list(table.columns) == [
        "Maternal mortality ratio [Sex=Female]",
        "Proportion of population with access to electricity",
    ]
    assert table.loc["Bangladesh", "Maternal mortality ratio [Sex=Female]"] == pytest.approx(115.1)
    assert "SDG Global Database" in un.cite(table)


def test_wide_keeps_years_when_there_are_several(fake: FakeAPI) -> None:
    table = un.get(MMR, "Bangladesh", years=(2022, 2023), wide=True)

    assert table.index.names == ["country", "year"]


def test_wide_on_an_empty_table(fake: FakeAPI) -> None:
    with pytest.warns(un.MissingDataWarning):
        table = un.get(MMR, "Norway", wide=True)

    assert table.empty


# ── 5. Freshness ─────────────────────────────────────────────────────────


def test_since_drops_old_values_and_says_so(fake: FakeAPI) -> None:
    with pytest.warns(un.StaleDataWarning, match=r"Nepal \(2018\)"):
        table = un.latest(ELEC, ["Bangladesh", "Nepal"], since=2020)

    assert list(table["country"]) == ["Bangladesh"]
    assert table.attrs["stale"] == [
        {
            "country": "Nepal",
            "indicator_name": "Proportion of population with access to electricity",
            "year": 2018,
        }
    ]


# ── 6. Change over time ──────────────────────────────────────────────────


def test_change_compares_two_years(fake: FakeAPI) -> None:
    with pytest.warns(un.MissingDataWarning, match="Nepal"):
        table = un.change(MMR, ["Bangladesh", "Nepal"], 2019, 2023)

    row = table.iloc[0]
    assert (row["country"], row["start_value"], row["end_value"]) == ("Bangladesh", 160, 115.1)
    assert row["change"] == pytest.approx(-44.9)
    assert row["change_pct"] == pytest.approx(-28.0625)
    assert "Nepal" in {m["country"] for m in table.attrs["missing"]}


def test_change_needs_years_in_order(fake: FakeAPI) -> None:
    with pytest.raises(ValueError, match="must be earlier"):
        un.change(MMR, "Bangladesh", 2023, 2015)


# ── 7. Better search ─────────────────────────────────────────────────────


def test_search_collapses_breakdowns_into_their_total(fake: FakeAPI) -> None:
    table = un.search("under-five mortality")

    assert list(table["indicator"]) == ["undata/who/U5", "undata/who/INFANT.WEALTH--Q1"]
    assert list(table["breakdowns"]) == [2, 0]
    assert table.loc[0, "places"] == 90
    assert table.loc[0, "years"] == "1993-2020"


def test_search_can_list_every_breakdown_without_coverage(fake: FakeAPI) -> None:
    table = un.search("under-five mortality", breakdowns=True, coverage=False)

    assert len(table) == 3
    assert list(table.columns) == ["indicator", "name", "source"]
    assert fake.calls["variable_info"] == 0


# ── 8. Charts ────────────────────────────────────────────────────────────


@pytest.fixture
def no_display(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MPLBACKEND", "Agg")


def test_chart_draws_ranked_bars_with_a_source_line(
    fake: FakeAPI, tmp_path: Path, no_display: None
) -> None:
    with pytest.warns(un.MixedYearsWarning):
        table = un.latest(ELEC, ["Bangladesh", "Nepal"])

    fig = un.chart(table, tmp_path / "bars.png", highlight="Nepal")

    assert (tmp_path / "bars.png").stat().st_size > 1000
    texts = " ".join(t.get_text() for t in fig.texts)
    assert "Source: UN_SDG (Data Commons copy)" in texts


def test_chart_picks_lines_for_several_years_and_dumbbells_for_change(
    fake: FakeAPI, tmp_path: Path, no_display: None
) -> None:
    series = un.get(MMR, "Bangladesh")
    un.chart(series, tmp_path / "line.svg")
    with pytest.warns(un.MissingDataWarning):
        moved = un.change(MMR, ["Bangladesh", "Nepal"], 2019, 2023)
    un.chart(moved, tmp_path / "dumbbell.png", highlight=["Bangladesh"])

    assert (tmp_path / "line.svg").read_text().startswith("<?xml")
    assert (tmp_path / "dumbbell.png").exists()


def test_chart_refuses_two_indicators_and_too_many_lines(fake: FakeAPI, no_display: None) -> None:
    with pytest.warns(un.MixedYearsWarning):
        two = un.latest([ELEC, MMR], ["Bangladesh", "Nepal"])
    with pytest.raises(ValueError, match="one indicator at a time"):
        un.chart(two)

    many = pd.DataFrame(
        {
            "country": [f"C{i}" for i in range(7) for _ in range(2)],
            "year": [2020, 2021] * 7,
            "value": 1.0,
            "indicator_name": "x",
            "unit": "%",
            "source": "s",
        }
    )
    with pytest.raises(ValueError, match="too many lines"):
        un.chart(many)
    with pytest.raises(ValueError, match=r"needs a table from un\.change"):
        un.chart(many, kind="dumbbell")
    with pytest.raises(ValueError, match="empty"):
        un.chart(many.iloc[0:0])


# ── 9. Breakdowns ────────────────────────────────────────────────────────


def test_breakdowns_list_slices_with_readable_values(fake: FakeAPI) -> None:
    table = un.breakdowns(TOTN)

    assert list(table["indicator"]) == [TOTN, f"{TOTN}.SEX--F", f"{TOTN}.SEX--M", f"{TOTN}.SEX--_U"]
    assert list(table["sex"].iloc[1:]) == ["Female", "Male", "Unknown"]


def test_get_by_a_breakdown_adds_its_column(fake: FakeAPI) -> None:
    table = un.get(TOTN, "Bangladesh", by="sex")

    assert list(table.columns)[6] == "sex"
    assert dict(zip(table["sex"], table["value"], strict=True)) == {
        "Female": 4,
        "Male": 9,
        "Unknown": 2,
    }


def test_a_breakdown_that_does_not_exist_says_what_does(fake: FakeAPI) -> None:
    with pytest.raises(ValueError, match=r"no breakdown by 'age'\. Breakdowns it has: sex"):
        un.get(TOTN, "Bangladesh", by="age")


def test_an_indicator_outside_any_group_has_no_breakdowns(fake: FakeAPI) -> None:
    assert un.breakdowns(ELEC).empty


# ── 10. Honest comparisons ───────────────────────────────────────────────


def test_compare_spells_out_who_has_what(fake: FakeAPI) -> None:
    with (
        pytest.warns(un.MixedYearsWarning),
        pytest.warns(un.CoverageWarning, match=r"2 of 3 countries have all 2 indicators") as caught,
    ):
        table = un.compare({"power": ELEC, "mothers": MMR}, ["Bangladesh", "Nepal", "Norway"])

    assert list(table.columns) == [
        "country",
        "iso3",
        "power",
        "power year",
        "mothers",
        "mothers year",
    ]
    assert list(table["country"]) == ["Bangladesh", "Nepal"]
    assert table.loc[1, "power year"] == 2018
    assert table.attrs["coverage"] == {
        "all": ["Bangladesh", "Nepal"],
        "only": {"power": [], "mothers": []},
        "none": ["Norway"],
    }
    assert any("No data at all for 1" in str(w.message) for w in caught)
    assert "SDG Global Database" in un.cite(table)


def test_compare_without_labels_uses_indicator_names(fake: FakeAPI) -> None:
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        table = un.compare([MMR], ["Bangladesh"])

    assert "Maternal mortality ratio [Sex=Female]" in table.columns


# ── 11. Plain-English summaries ──────────────────────────────────────────


def test_describe_latest_values(fake: FakeAPI) -> None:
    with pytest.warns(un.MixedYearsWarning):
        table = un.latest(ELEC, ["Bangladesh", "Nepal"])

    assert un.describe(table) == (
        "Proportion of population with access to electricity: highest in Bangladesh "
        "(99.5%, 2024) and lowest in Nepal (90.0%, 2018); the median across 2 places is "
        "94.8%. Values are from 2018 to 2024."
    )


def test_describe_a_series_and_a_change(fake: FakeAPI) -> None:
    series = un.get(MMR, "Bangladesh")
    assert "Bangladesh fell from 160 in 2019 to 115 in 2023 (-28%)." in un.describe(series)
    assert "(count per 100,000 live births)" in un.describe(series)

    with pytest.warns(un.MissingDataWarning):
        moved = un.change(MMR, ["Bangladesh", "Nepal"], 2019, 2023)
    text = un.describe(moved)
    assert "fell in all 1 places. The largest fall was in Bangladesh (-28%)." in text
    assert "No data for Nepal; they are not counted as zero." in text


def test_describe_odd_inputs(fake: FakeAPI) -> None:
    with pytest.raises(ValueError, match="works on tables"):
        un.describe(pd.DataFrame({"a": [1]}))
    with pytest.warns(un.MissingDataWarning):
        empty = un.get(MMR, "Norway")
    assert "empty" in un.describe(empty)


# ── 12. Metadata links ───────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("number", "url"),
    [
        ("3.1.1", "Metadata-03-01-01.pdf"),
        ("16.10.2", "Metadata-16-10-02.pdf"),
        ("4.a.1", "Metadata-04-0a-01.pdf"),
    ],
)
def test_metadata_urls(number: str, url: str) -> None:
    assert metadata_url(number).endswith(url)


def test_about_without_an_sdg_link(fake: FakeAPI) -> None:
    info = un.about(ELEC)

    assert info.sdg_indicator == ""
    assert "definition" not in repr(info)


# ── 13. Disk cache ───────────────────────────────────────────────────────


@respx.mock
def test_the_cache_answers_a_repeated_request(tmp_path: Path) -> None:
    route = respx.get(f"{BASE}/x").mock(return_value=httpx.Response(200, json={"a": 1}))
    with Transport(base_url=BASE, cache_dir=tmp_path) as t:
        assert t.get("/x") == {"a": 1}
        assert t.get("/x") == {"a": 1}
        assert route.call_count == 1
        assert t.clear_cache() == 1
        t.get("/x")
    assert route.call_count == 2


@respx.mock
def test_a_stale_cache_entry_is_fetched_again(tmp_path: Path) -> None:
    route = respx.post(f"{BASE}/y").mock(return_value=httpx.Response(200, json=[1]))
    with Transport(base_url=BASE, cache_dir=tmp_path, cache_hours=0) as t:
        t.post("/y", {"q": 1})
        t.post("/y", {"q": 1})
    assert route.call_count == 2


def test_errors_are_never_cached_and_an_empty_cache_clears_nothing(tmp_path: Path) -> None:
    assert Transport(base_url=BASE, cache_dir=tmp_path / "none").clear_cache() == 0
    assert Transport(base_url=BASE).clear_cache() == 0


def test_configure_turns_the_cache_on(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from undata import _session

    monkeypatch.setattr(_session._State, "transport", None)
    un.configure(cache=tmp_path)
    assert _session.transport().cache_dir == tmp_path
    un.configure(cache=True)
    assert _session.transport().cache_dir is not None
    assert un.clear_cache() >= 0
    un.configure()
    assert _session.transport().cache_dir is None
    _session.transport().close()


# ── 14. Command line ─────────────────────────────────────────────────────


def run(args: list[str], capsys: pytest.CaptureFixture[str]) -> tuple[int, str, str]:
    code = cli.main(args)
    out, err = capsys.readouterr()
    return code, out, err


def test_cli_get_saves_a_file(
    fake: FakeAPI, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code, out, _ = run(
        ["get", "3.1.1", "Bangladesh", "--years", "2022-2023", "--to", str(tmp_path / "x.csv")],
        capsys,
    )

    assert code == 0
    assert "Saved 2 rows" in out
    assert pd.read_csv(tmp_path / "x.csv")["year"].tolist() == [2022, 2023]


def test_cli_prints_tables_and_sentences(fake: FakeAPI, capsys: pytest.CaptureFixture[str]) -> None:
    code, out, err = run(
        ["change", MMR, "Bangladesh", "Nepal", "--start", "2019", "--end", "2023", "--describe"],
        capsys,
    )

    assert code == 0
    assert "Bangladesh" in out
    assert "largest fall" in out
    assert "Note: No data for 1" in err


@pytest.mark.parametrize(
    ("args", "expected"),
    [
        (["search", "maternal mortality"], "SH_STA_MORT"),
        (["about", "3.1.1"], "Metadata-03-01-01.pdf"),
        (["latest", ELEC, "Bangladesh", "--since", "2020"], "99.5"),
        (["latest", ELEC, "Bangladesh", "--wide"], "Proportion of population"),
        (["totals", MMR, "World", "--latest"], "197.3"),
        (["get", TOTN, "Bangladesh", "--by", "sex"], "Female"),
        (["countries", "Southern Asia"], "Nepal"),
        (["regions"], "Least developed countries"),
        (["sdg"], "Promote peaceful"),
        (["sdg", "16"], "16.10"),
        (["sdg", "3.1"], "3.1.1"),
        (["sdg", "16.1.2"], "VC_DTH_TOTR"),
        (["powerquery", "3.1.1", "Bangladesh", "--years", "2023"], "Web.Contents"),
    ],
)
def test_cli_commands(
    fake: FakeAPI, capsys: pytest.CaptureFixture[str], args: list[str], expected: str
) -> None:
    code, out, _ = run(args, capsys)

    assert code == 0
    assert expected in out


def test_cli_reports_errors_without_a_traceback(
    fake: FakeAPI, capsys: pytest.CaptureFixture[str]
) -> None:
    code, _, err = run(["get", "maternal mortality", "Nepal"], capsys)

    assert code == 1
    assert err.startswith("Error: 'maternal mortality' looks like a description")


def test_cli_clears_the_cache(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("undata.cli.clear_cache", lambda: 3)
    code, out, _ = run(["cache", "clear"], capsys)

    assert (code, out.strip()) == (0, "Deleted 3 cached responses.")


# ── 15. Power Query ──────────────────────────────────────────────────────


def test_powerquery_names_the_ids_it_resolved(fake: FakeAPI) -> None:
    code = un.powerquery("3.1.1", ["Bangladesh", "Nepal"], years=(2015, 2023))

    assert 'Variables = {"undata/sdg/SH_STA_MORT.SEX--F"}' in code
    assert 'Entities  = {"country/BGD", "country/NPL"}' in code
    assert '#"country/BGD" = "Bangladesh"' in code
    assert 'List.Contains({"2015", "2016"' in code
    assert code.count("let") == 1
    assert code.rstrip().endswith("Result")


def test_powerquery_without_years_keeps_every_year(fake: FakeAPI) -> None:
    assert "InYears    = AddYear," in un.powerquery(MMR, "Bangladesh")


# ── 16. AI-ready export ──────────────────────────────────────────────────


def test_for_ai_carries_instructions_sources_and_gaps(fake: FakeAPI) -> None:
    with pytest.warns(un.MissingDataWarning):
        table = un.latest(MMR, ["Bangladesh", "Norway"])

    text = un.for_ai(table)

    assert "Use only the numbers in this table" in text
    assert "| Bangladesh" in text  # a Markdown table
    assert "No data for: Norway." in text
    assert "- SDG Global Database. Maternal mortality ratio" in text


def test_for_ai_without_tabulate_or_sources(fake: FakeAPI, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("undata.export._has_tabulate", lambda: False)
    table = un.get(MMR, "Bangladesh")

    text = un.for_ai(table, max_rows=2)
    assert "country,iso3,year" in text
    assert "(Showing 2 of 5 rows.)" in text
    assert "Sources:" not in un.for_ai(pd.DataFrame({"country": ["x"]}))


# ── Fixes: paging, parallel fetching ─────────────────────────────────────


@respx.mock
def test_a_failure_deep_in_paging_explains_itself(transport: Transport) -> None:
    respx.get(f"{BASE}/core/api/v2/node").mock(
        side_effect=[
            httpx.Response(200, json={"data": {}, "nextToken": "t"}),
            httpx.Response(500, text="boom"),
            httpx.Response(500, text="boom"),
            httpx.Response(500, text="boom"),
        ]
    )

    with pytest.raises(un.APIError, match="failed on page 2 of a very large answer"):
        ep.node(transport, "Earth", "<-containedInPlace")


@respx.mock
def test_a_client_error_while_paging_is_passed_through(transport: Transport) -> None:
    respx.get(f"{BASE}/core/api/v2/node").mock(
        side_effect=[httpx.Response(200, json={"data": {}, "nextToken": "t"}), httpx.Response(400)]
    )

    with pytest.raises(un.APIError, match="malformed"):
        ep.node(transport, "Earth", "<-containedInPlace")


def test_many_places_are_fetched_in_parallel_chunks(
    fake: FakeAPI, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("undata.data._CHUNK", 1)

    with pytest.warns(un.MissingDataWarning):
        table = un.get(MMR, "LDCs")

    assert fake.calls["series"] == 3
    assert set(table["country"]) == {"Bangladesh", "Nepal"}
