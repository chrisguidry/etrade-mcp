"""
Test the server's tool set and how it starts.
"""

import runpy
import sys
from unittest.mock import patch

import fastmcp
import mcp.types as mt
import pytest
from conftest import FakeETrade

from etrade_mcp.effects import READ, WRITE
from etrade_mcp.repository import ETradeRepository


@pytest.fixture(autouse=True)
def server_not_imported(monkeypatch: pytest.MonkeyPatch) -> None:
    """runpy executes the module's code afresh, and warns when an imported copy
    of the module is already in sys.modules, as conftest's import leaves one."""
    monkeypatch.delitem(sys.modules, "etrade_mcp.server")


async def served_tools() -> list[mt.Tool]:
    module = runpy.run_module("etrade_mcp.server")
    async with fastmcp.Client(module["mcp"]) as client:
        tools: list[mt.Tool] = await client.list_tools()
    return tools


async def test_every_tool_is_tagged_read_or_write() -> None:
    tools = await served_tools()

    tags = [set(tool.meta["fastmcp"]["tags"]) for tool in tools if tool.meta]
    assert len(tags) == len(tools)
    assert all(len(tool_tags & {READ, WRITE}) == 1 for tool_tags in tags)


async def test_every_tool_only_reads() -> None:
    tools = await served_tools()

    assert all(tool.annotations for tool in tools)
    assert all(tool.annotations.read_only_hint for tool in tools if tool.annotations)


async def test_every_tool_has_a_title() -> None:
    tools = await served_tools()

    assert all(tool.title for tool in tools)


async def test_parameter_descriptions_carry_no_docstring_indentation() -> None:
    """A wrapped Args line needs a 4-space hanging indent.  Aligned
    indentation survives FastMCP's docstring parsing and reaches the model."""
    tools = await served_tools()

    descriptions = [
        f"{tool.name}.{name}: {schema['description']!r}"
        for tool in tools
        for name, schema in tool.input_schema["properties"].items()
        if "\n " in schema.get("description", "")
    ]
    assert descriptions == []


def test_running_the_module_authorizes_every_profile_then_serves(
    etrade: FakeETrade, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ETRADE_1_CONSUMER_KEY", "key1")
    monkeypatch.setenv("ETRADE_1_CONSUMER_SECRET", "secret1")
    authorized: list[str] = []

    def authorize(repository: ETradeRepository) -> None:
        authorized.append(repository.profile_id)

    with (
        patch("etrade_mcp.repository.ETradeRepository.authorize", authorize),
        patch("fastmcp.FastMCP.run") as run,
    ):
        runpy.run_module("etrade_mcp.server", run_name="__main__")

    assert authorized == ["0", "1"]
    run.assert_called_once_with()


def test_importing_the_server_does_not_start_it() -> None:
    with patch("fastmcp.FastMCP.run") as run:
        runpy.run_module("etrade_mcp.server")

    run.assert_not_called()
