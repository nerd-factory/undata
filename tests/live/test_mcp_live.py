"""The MCP connector against the real platform, through a real MCP client."""

from __future__ import annotations

from typing import Any

import anyio
import pytest

pytest.importorskip("mcp")

from mcp import Client

from undata.mcp_server import server

pytestmark = pytest.mark.live


def call(name: str, **arguments: Any) -> Any:
    async def main() -> Any:
        async with Client(server) as client:
            return await client.call_tool(name, arguments)

    return anyio.run(main)


def test_an_assistant_can_go_from_words_to_a_progress_assessment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MPLBACKEND", "Agg")
    found = call("undata_search_indicators", query="maternal mortality ratio", limit=5)
    assessed = call(
        "undata_assess_progress",
        indicator="3.1.1",
        places=["Southern Asia"],
        better="lower",
        target=70,
        include_chart=True,
    )

    assert "undata/sdg/SH_STA_MORT.SEX--F" in found.content[0].text
    assert not assessed.is_error
    assert [c.type for c in assessed.content] == ["text", "image"]
    assert "Bangladesh" in assessed.content[0].text
