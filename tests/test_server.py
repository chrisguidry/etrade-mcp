"""Tests for MCP server tools."""

import json
import sys
from decimal import Decimal
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastmcp.client import Client, FastMCPTransport

# Add parent directory to path to import modules
sys.path.insert(0, str(Path(__file__).parent.parent))

import server
from models import Quote
from repository import ETradeRepository


async def test_list_accounts(
    mock_repository_context: MagicMock,
    mcp_client: Client[FastMCPTransport],
) -> None:
    """Test list_accounts tool."""
    result = await mcp_client.call_tool("list_accounts", arguments={})
    response_data = json.loads(result.content[0].text)  # type: ignore[union-attr]

    assert len(response_data["accounts"]) == 1
    assert response_data["accounts"][0]["account_id"] == "12345678"
    assert response_data["accounts"][0]["account_id_key"] == "abc123xyz"
    mock_repository_context.get_accounts.assert_called_once()


async def test_get_account_balance(
    mock_repository_context: MagicMock,
    mcp_client: Client[FastMCPTransport],
) -> None:
    """Test get_account_balance tool."""
    result = await mcp_client.call_tool(
        "get_account_balance", arguments={"account_id_key": "abc123xyz"}
    )
    response_data = json.loads(result.content[0].text)  # type: ignore[union-attr]

    assert response_data["account_id"] == "12345678"
    assert response_data["cash_balance"] == "5000.00"
    assert response_data["total_account_value"] == "25000.00"
    mock_repository_context.get_account_balance.assert_called_once_with("abc123xyz")


async def test_get_account_portfolio(
    mock_repository_context: MagicMock,
    mcp_client: Client[FastMCPTransport],
) -> None:
    """Test get_account_portfolio tool."""
    result = await mcp_client.call_tool(
        "get_account_portfolio", arguments={"account_id_key": "abc123xyz"}
    )
    response_data = json.loads(result.content[0].text)  # type: ignore[union-attr]

    assert response_data["account_id"] == "abc123xyz"
    assert len(response_data["positions"]) == 1
    assert response_data["positions"][0]["symbol"] == "AAPL"
    assert response_data["total_market_value"] == "1750.00"
    mock_repository_context.get_account_portfolio.assert_called_once_with("abc123xyz")


async def test_get_quotes(
    mock_repository_context: MagicMock,
    mcp_client: Client[FastMCPTransport],
) -> None:
    """Test get_quotes tool with single symbol."""
    result = await mcp_client.call_tool("get_quotes", arguments={"symbols": ["AAPL"]})
    response_data = json.loads(result.content[0].text)  # type: ignore[union-attr]

    assert len(response_data["quotes"]) == 1
    assert response_data["quotes"][0]["symbol"] == "AAPL"
    assert response_data["quotes"][0]["last_trade"] == "175.00"
    mock_repository_context.get_quotes.assert_called_once_with(["AAPL"])


async def test_get_quotes_multiple_symbols(
    mock_repository_context: MagicMock,
    mcp_client: Client[FastMCPTransport],
) -> None:
    """Test get_quotes tool with multiple symbols."""
    quote1 = Quote(symbol="AAPL", last_trade=Decimal("175.00"))
    quote2 = Quote(symbol="MSFT", last_trade=Decimal("380.00"))
    mock_repository_context.get_quotes.return_value = [quote1, quote2]

    result = await mcp_client.call_tool(
        "get_quotes", arguments={"symbols": ["AAPL", "MSFT"]}
    )
    response_data = json.loads(result.content[0].text)  # type: ignore[union-attr]

    assert len(response_data["quotes"]) == 2
    assert response_data["quotes"][0]["symbol"] == "AAPL"
    assert response_data["quotes"][1]["symbol"] == "MSFT"


async def test_get_quotes_too_many_symbols(
    mock_repository_context: MagicMock,
    mcp_client: Client[FastMCPTransport],
) -> None:
    """Test get_quotes tool rejects > 25 symbols."""
    symbols = [f"SYM{i}" for i in range(26)]

    with pytest.raises(Exception, match="Maximum 25 symbols"):
        await mcp_client.call_tool("get_quotes", arguments={"symbols": symbols})


@patch("server._repositories", {})
@patch("server.create_repositories_from_env")
def test_get_repository_already_authorized(
    mock_create: MagicMock, temp_config_home: Path
) -> None:
    """Test get_repository doesn't re-authorize if already authorized."""
    mock_repo = MagicMock(spec=ETradeRepository)
    # Set _is_authorized as a direct attribute (not a MagicMock)
    type(mock_repo)._is_authorized = True
    mock_create.return_value = {"0": mock_repo}

    repo = server.get_repository()

    assert repo._is_authorized
    mock_repo.authorize.assert_not_called()
    # Reset module state for other tests
    server._repositories = {}
    # Clean up the class attribute
    del type(mock_repo)._is_authorized


@patch("server._repositories", {})
@patch("server.create_repositories_from_env")
def test_get_repository_needs_authorization(
    mock_create: MagicMock, temp_config_home: Path
) -> None:
    """Test get_repository calls authorize if not authorized."""
    mock_repo = MagicMock(spec=ETradeRepository)
    # Set _is_authorized as a direct attribute (not a MagicMock)
    type(mock_repo)._is_authorized = False
    mock_create.return_value = {"0": mock_repo}

    server.get_repository()

    mock_repo.authorize.assert_called_once()
    # Reset module state for other tests
    server._repositories = {}
    # Clean up the class attribute
    del type(mock_repo)._is_authorized


@patch("server._repositories", {})
@patch("server.create_repositories_from_env")
def test_get_repository_invalid_profile(
    mock_create: MagicMock, temp_config_home: Path
) -> None:
    """Test get_repository raises error for invalid profile_id."""
    mock_repo = MagicMock(spec=ETradeRepository)
    type(mock_repo)._is_authorized = True
    mock_create.return_value = {"0": mock_repo}

    with pytest.raises(ValueError, match="Profile 999 not found"):
        server.get_repository(profile_id="999")

    # Reset module state for other tests
    server._repositories = {}
    # Clean up the class attribute
    del type(mock_repo)._is_authorized
