import os
import sys
from pathlib import Path

import anyio
import pytest
from mcp import Client, StdioServerParameters

from neurisko.mcp.paths import WORKSPACE_ENV
from neurisko.mcp.server import build_server

RS = "rulesets/monster-mash.toml"
TOOLS = {
    "check_ruleset",
    "simulate_battle",
    "score_team",
    "quick_balance",
    "verify_patch",
    "start_report",
    "report_status",
}


def run(coro_fn):
    return anyio.run(coro_fn)


def test_in_memory_server(workspace):
    async def main():
        async with Client(build_server()) as c:
            tools = {t.name: t for t in (await c.list_tools()).tools}
            assert set(tools) == TOOLS
            assert tools["verify_patch"].input_schema["properties"]["field"]["enum"][0] == "cost"
            r = await c.call_tool("check_ruleset", {"path": RS})
            assert not r.is_error and r.structured_content["valid"] is True
            r = await c.call_tool("score_team", {"path": RS, "team": ["zombie", "ghost"]})
            assert not r.is_error and 0 <= r.structured_content["score"] <= 1
            bad = await c.call_tool("check_ruleset", {"path": "../etc/passwd.toml"})
            assert bad.is_error and "outside the workspace" in bad.content[0].text
            bad = await c.call_tool(
                "verify_patch", {"path": RS, "unit": "witch", "field": "mana", "new_value": 1}
            )
            assert bad.is_error
            st = await c.call_tool("report_status", {"job_id": "nope"})
            assert st.structured_content["state"] == "unknown"
            prompts = (await c.list_prompts()).prompts
            assert [p.name for p in prompts] == ["balance_review"]
            msg = await c.get_prompt("balance_review", {"path": RS})
            text = msg.messages[0].content.text
            assert "verify_patch" in text and RS in text

    run(main)


def test_stdio_entry_point(workspace):
    """The real process Kiro starts: `neurisko-mcp` over stdio."""
    exe = Path(sys.executable).with_name("neurisko-mcp")
    if not exe.exists():
        pytest.skip("console script not installed")
    params = StdioServerParameters(
        command=str(exe), args=[], env={**os.environ, WORKSPACE_ENV: str(workspace)}
    )

    async def main():
        async with Client(params) as c:
            assert {t.name for t in (await c.list_tools()).tools} == TOOLS
            r = await c.call_tool(
                "simulate_battle",
                {
                    "path": RS,
                    "team_a": ["ghost", "pumpkin_mage"],
                    "team_b": ["gargoyle", "werewolf"],
                    "seed": 3,
                },
            )
            assert not r.is_error and r.structured_content["winner"] == "B"

    run(main)
