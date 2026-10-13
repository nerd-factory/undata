"""The MCP connector, driven by a real MCP client against the fake platform."""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from typing import Any

import anyio
import pytest

pytest.importorskip("mcp")

from mcp import Client
from mcp.types import CallToolResult

from undata import mcp_server
from undata.mcp_server import server

from .fake_api import ELEC, MMR, TOTN, FakeAPI


@pytest.fixture(autouse=True)
def agg_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MPLBACKEND", "Agg")


def run(body: Callable[[Client], Awaitable[Any]]) -> Any:
    async def main() -> Any:
        async with Client(server) as client:
            return await body(client)

    return anyio.run(main)


def call(name: str, **arguments: Any) -> CallToolResult:
    async def body(client: Client) -> CallToolResult:
        return await client.call_tool(name, arguments)

    result: CallToolResult = run(body)
    return result


def text(result: CallToolResult) -> str:
    return "\n".join(c.text for c in result.content if c.type == "text")


def test_every_tool_is_read_only_and_explained() -> None:
    async def body(client: Client) -> Any:
        return await client.list_tools()

    tools = run(body).tools
    assert len(tools) == 14
    for tool in tools:
        assert tool.name.startswith("undata_")
        assert tool.annotations is not None
        assert tool.annotations.read_only_hint is True
        assert tool.annotations.destructive_hint is False
        assert tool.description, tool.name
        assert len(tool.description) > 40, tool.name


def test_search_returns_ids_to_use_next(fake: FakeAPI) -> None:
    result = call("undata_search_indicators", query="maternal mortality", limit=5)

    assert not result.is_error
    assert MMR in text(result)
    assert "| indicator |" in text(result)


def test_data_carries_header_summary_notes_and_sources(fake: FakeAPI) -> None:
    result = call("undata_latest_values", indicators=[ELEC], places=["Bangladesh", "Nepal"])

    body = text(result)
    assert "**Unit:** Percent" in body
    assert "| Nepal | 2018 | 90 |" in body
    assert "**Notes:**" in body  # the years differ, and the assistant is told
    assert "**Sources:**" in body


def test_json_pages_through_rows(fake: FakeAPI) -> None:
    first = json.loads(
        text(
            call(
                "undata_get_data",
                indicators=[MMR],
                places=["Bangladesh"],
                limit=2,
                response_format="json",
            )
        )
    )
    second = json.loads(
        text(
            call(
                "undata_get_data",
                indicators=[MMR],
                places=["Bangladesh"],
                limit=2,
                offset=first["next_offset"],
                response_format="json",
            )
        )
    )

    assert first["total_rows"] == 5
    assert [r["year"] for r in first["rows"]] == [2019, 2020]
    assert first["has_more"] is True
    assert [r["year"] for r in second["rows"]] == [2021, 2022]
    assert first["unit"] == "Count per 100,000 live births"


def test_markdown_says_how_to_get_the_next_page(fake: FakeAPI) -> None:
    body = text(
        call(
            "undata_get_data",
            indicators=[MMR],
            places=["Bangladesh"],
            start_year=2019,
            end_year=2023,
            limit=3,
        )
    )
    assert "Rows 1-3 of 5. Ask again with offset=3 for more." in body


def test_analyses_answer_with_the_finding_and_a_chart(fake: FakeAPI) -> None:
    result = call(
        "undata_assess_progress",
        indicator=MMR,
        places=["Bangladesh", "Nepal"],
        better="lower",
        target=70,
        include_chart=True,
    )

    assert [c.type for c in result.content] == ["text", "image"]
    assert result.content[1].mime_type == "image/png"  # type: ignore[union-attr]
    assert "Technical Note for Progress Assessment" in text(result)


@pytest.mark.parametrize(
    ("name", "arguments", "expected"),
    [
        (
            "undata_country_profile",
            {"country": "Bangladesh", "indicators": [MMR, ELEC]},
            "Southern Asia",
        ),
        (
            "undata_group_gap",
            {"indicator": TOTN, "places": ["Bangladesh"]},
            "the widest gap is in Bangladesh",
        ),
        (
            "undata_group_totals",
            {"indicators": [MMR], "places": ["World"]},
            "| World | 2023 | 197 |",
        ),
        ("undata_benchmark_groups", {"indicator": MMR, "places": ["World"]}, "World"),
        (
            "undata_change_over_time",
            {"indicator": MMR, "places": ["Bangladesh"], "start_year": 2019, "end_year": 2023},
            "-28",
        ),
        (
            "undata_compare_indicators",
            {"indicators": [MMR, ELEC], "places": ["Bangladesh", "Nepal"]},
            "Bangladesh",
        ),
        (
            "undata_check_availability",
            {"indicators": [MMR, ELEC], "places": ["Bangladesh", "Nepal"]},
            "| Nepal | 2022 | 2018 |",
        ),
        ("undata_list_places", {"region": "LDCs"}, "Bangladesh"),
        ("undata_list_places", {}, "Least developed countries"),
        ("undata_browse_sdg", {}, "| 3 | Ensure healthy lives |"),
        ("undata_browse_sdg", {"code": "16.1"}, "16.1.2"),
        ("undata_describe_indicator", {"indicator": TOTN}, "- sex: Female; Male; Unknown"),
    ],
)
def test_each_tool_answers(
    fake: FakeAPI, name: str, arguments: dict[str, Any], expected: str
) -> None:
    result = call(name, **arguments)

    assert not result.is_error, text(result)
    assert expected in text(result)


def test_errors_point_to_the_tool_that_helps(fake: FakeAPI) -> None:
    unknown = call("undata_list_places", region="Atlantis")
    bad_code = call("undata_browse_sdg", code="1.2.3.4")

    assert unknown.is_error
    assert "Run undata_list_places" in text(unknown)
    assert "un.countries" not in text(unknown)
    assert bad_code.is_error
    assert "goal, target or indicator number" in text(bad_code)


def test_a_chart_that_cannot_be_drawn_is_explained_not_fatal(fake: FakeAPI) -> None:
    result = call(
        "undata_check_availability", indicators=[MMR], places=["Norway"], include_chart=True
    )

    assert not result.is_error
    assert "_No chart:" in text(result) or [c.type for c in result.content] == ["text", "image"]


def test_main_configures_the_cache_and_serves_stdio(monkeypatch: pytest.MonkeyPatch) -> None:
    served: list[tuple[Any, ...]] = []
    configured: list[dict[str, Any]] = []
    monkeypatch.setattr(server, "run", lambda *a, **k: served.append((a, k)))
    monkeypatch.setattr("undata._session.configure", lambda **k: configured.append(k))

    mcp_server.main([])
    mcp_server.main(["--http", "--port", "9000", "--no-cache"])

    assert served[0] == (("stdio",), {})
    assert served[1][0] == ("streamable-http",)
    assert served[1][1]["port"] == 9000
    assert configured == [{"cache": True}, {"cache": False}]


def test_the_evaluation_set_is_valid_xml_with_ten_questions() -> None:
    import xml.etree.ElementTree as ET
    from pathlib import Path

    path = Path(__file__).resolve().parents[1] / "evals" / "undata_mcp_evaluation.xml"
    pairs = ET.parse(path).getroot().findall("qa_pair")  # noqa: S314 — our own file

    assert len(pairs) == 10
    assert all(p.findtext("question") and p.findtext("answer") for p in pairs)
