from __future__ import annotations

import warnings
from pathlib import Path

import pandas as pd
import pytest

import undata as un

from .fake_api import MMR, FakeAPI

# ── SDG ────────────────────────────────────────────────────────────────


def test_goals_are_numbered_and_sorted_numerically(fake: FakeAPI) -> None:
    table = un.sdg.goals()

    assert list(table["goal"]) == ["3", "16"]
    assert table["name"].iloc[1] == "Promote peaceful and inclusive societies"


def test_targets_sort_numbers_before_letters(fake: FakeAPI) -> None:
    assert list(un.sdg.targets(16)["target"]) == ["16.1", "16.10", "16.a"]
    assert list(un.sdg.targets("16")["target"]) == ["16.1", "16.10", "16.a"]


def test_indicators_under_a_target(fake: FakeAPI) -> None:
    table = un.sdg.indicators("16.1")

    assert list(table["indicator"]) == ["16.1.1", "16.1.2"]
    assert table["name"].iloc[1] == "Conflict-related deaths"


def test_series_lists_fetchable_ids_totals_first_without_duplicates(fake: FakeAPI) -> None:
    table = un.sdg.series("16.1.2")

    assert list(table.columns) == ["indicator", "name", "total"]
    assert list(table["indicator"]) == [
        "undata/sdg/VC_DTH_TOTN",
        "undata/sdg/VC_DTH_TOTR",
        "undata/sdg/VC_DTH_TOTN.SEX--F",
        "undata/sdg/VC_DTH_TOTN.SEX--M",
        "undata/sdg/VC_DTH_TOTN.SEX--_U",
    ]
    assert list(table["total"]) == [True, True, False, False, False]


def test_an_indicator_with_no_series_gives_an_empty_table(fake: FakeAPI) -> None:
    assert un.sdg.series("16.1.1").empty


@pytest.mark.parametrize(
    ("call", "code", "hint"),
    [
        (un.sdg.targets, "16.1", "goal number"),
        (un.sdg.indicators, "16", "target number"),
        (un.sdg.series, "16.1", "indicator number"),
        (un.sdg.series, "16..2", "indicator number"),
    ],
)
def test_sdg_numbers_are_checked(fake: FakeAPI, call: object, code: str, hint: str) -> None:
    with pytest.raises(ValueError, match=hint):
        call(code)  # type: ignore[operator]


# ── ask ────────────────────────────────────────────────────────────────


def test_ask_reports_a_guessed_place_and_warns(fake: FakeAPI) -> None:
    with pytest.warns(un.PlaceGuessedWarning, match="did not name"):
        answer = un.ask("child mortality in Bengal")

    assert answer.place == "United States of America"
    assert answer.place_id == "country/USA"
    assert answer.place_was_guessed
    assert answer.indicators[0] == ("undata/unicef/CME_MR.AGE--0", "Child mortality rate [0]")
    text = repr(answer)
    assert "GUESSED" in text
    assert "...and 2 more" in text
    assert "note          Low confidence" in text


def test_ask_with_a_named_place_is_quiet(fake: FakeAPI) -> None:
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        answer = un.ask("child mortality in Bangladesh")

    assert not answer.place_was_guessed
    assert "(from your question)" in repr(answer)


def test_an_answer_without_a_place() -> None:
    answer = un.Answer("q", None, None, place_was_guessed=False)

    assert "place         none" in repr(answer)


# ── cite and save ──────────────────────────────────────────────────────


def _table(fake: FakeAPI) -> pd.DataFrame:
    with pytest.warns(un.MissingDataWarning):
        return un.get(MMR, ["Bangladesh", "Norway"])


def test_cite_credits_the_source_and_the_platform(fake: FakeAPI) -> None:
    table = _table(fake)
    table.attrs["retrieved"] = "2026-10-13"

    assert un.cite(table) == (
        "SDG Global Database. Maternal mortality ratio [Sex=Female] "
        "(undata/sdg/SH_STA_MORT.SEX--F). https://unstats.un.org/sdgs/dataportal. "
        "Retrieved 2026-10-13 from the UN System Data Commons, https://data.un.org."
    )


def test_cite_needs_a_table_with_sources() -> None:
    with pytest.raises(ValueError, match="no source columns"):
        un.cite(pd.DataFrame({"a": [1]}))


def test_save_to_excel_adds_sources_and_gaps(fake: FakeAPI, tmp_path: Path) -> None:
    path = un.save(_table(fake), tmp_path / "out.xlsx")

    sheets = pd.read_excel(path, sheet_name=None)
    assert set(sheets) == {"data", "sources", "no data"}
    assert len(sheets["data"]) == 5
    assert sheets["sources"]["citation"].iloc[0].startswith("SDG Global Database.")
    assert list(sheets["no data"]["country"]) == ["Norway"]


def test_save_to_excel_without_gaps_has_two_sheets(fake: FakeAPI, tmp_path: Path) -> None:
    path = un.save(un.get(MMR, "Bangladesh"), tmp_path / "out.xlsx")

    assert set(pd.read_excel(path, sheet_name=None)) == {"data", "sources"}


def test_save_to_csv(fake: FakeAPI, tmp_path: Path) -> None:
    path = un.save(_table(fake), str(tmp_path / "out.csv"))

    assert pd.read_csv(path)["source"].iloc[0] == "SDG Global Database"


def test_save_rejects_other_formats(fake: FakeAPI, tmp_path: Path) -> None:
    with pytest.raises(ValueError, match=r"\.xlsx or \.csv"):
        un.save(_table(fake), tmp_path / "out.json")


# ── session ────────────────────────────────────────────────────────────


def test_configure_replaces_the_connection_and_clears_the_cache(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from undata import _session

    monkeypatch.setattr(_session._State, "transport", None)
    monkeypatch.setattr(_session._State, "cache", {"countries": "stale"})

    first = _session.transport()
    assert _session.transport() is first

    un.configure(timeout=5, base_url="https://example.test")

    assert _session._State.transport is not first
    assert _session._State.transport is not None
    assert _session._State.transport.base_url == "https://example.test"
    assert _session._State.cache == {}
    _session._State.transport.close()
