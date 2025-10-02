"""
Pytest configuration and shared fixtures for E*TRADE MCP tests.
"""

import sys
from collections.abc import AsyncGenerator, Generator
from decimal import Decimal
from pathlib import Path
from unittest.mock import MagicMock, patch

import fastmcp
import pytest
from fastmcp.client import Client, FastMCPTransport

# Add parent directory to path to import modules
sys.path.insert(0, str(Path(__file__).parent.parent))

import server
from models import Account, Balance, Portfolio, Position, Quote
from repository import ETradeRepository


@pytest.fixture
def temp_config_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Set XDG_CONFIG_HOME to a temporary directory for testing."""
    config_home = tmp_path / "config"
    config_home.mkdir()
    monkeypatch.setenv("XDG_CONFIG_HOME", str(config_home))
    return config_home


@pytest.fixture
def sample_account() -> Account:
    """Sample account for testing."""
    return Account(
        account_id="12345678",
        account_id_key="abc123xyz",
        account_mode="MARGIN",
        account_desc="Individual Brokerage",
        account_name="My Trading Account",
        account_type="INDIVIDUAL",
        institution_type="BROKERAGE",
        account_status="ACTIVE",
        closed_date=None,
        profile_id="0",
        profile_label="Test Profile",
    )


@pytest.fixture
def sample_balance() -> Balance:
    """Sample balance for testing."""
    return Balance(
        account_id="12345678",
        account_type="INDIVIDUAL",
        account_description="Individual Brokerage",
        account_mode="MARGIN",
        cash_balance=Decimal("5000.00"),
        cash_buying_power=Decimal("5000.00"),
        margin_buying_power=Decimal("10000.00"),
        total_account_value=Decimal("25000.00"),
        net_account_value=Decimal("25000.00"),
        uncleared_deposits=Decimal("0"),
        funds_withheld_from_purchase_power=Decimal("0"),
        funds_withheld_from_withdrawal=Decimal("0"),
        profile_id="0",
        profile_label="Test Profile",
    )


@pytest.fixture
def sample_position() -> Position:
    """Sample position for testing."""
    return Position(
        symbol="AAPL",
        symbol_description="APPLE INC COM",
        type_code="EQ",
        quantity=Decimal("10"),
        price_paid=Decimal("150.00"),
        total_cost=Decimal("1500.00"),
        cost_per_share=Decimal("150.00"),
        last_trade=Decimal("175.00"),
        market_value=Decimal("1750.00"),
        total_gain=Decimal("250.00"),
        total_gain_pct=Decimal("16.67"),
        days_gain=Decimal("10.00"),
        days_gain_pct=Decimal("0.57"),
        position_type="LONG",
        quote_detail="ALL",
    )


@pytest.fixture
def sample_portfolio(sample_position: Position) -> Portfolio:
    """Sample portfolio for testing."""
    return Portfolio(
        account_id="abc123xyz",
        positions=[sample_position],
        total_market_value=Decimal("1750.00"),
        profile_id="0",
        profile_label="Test Profile",
    )


@pytest.fixture
def sample_quote() -> Quote:
    """Sample quote for testing."""
    return Quote(
        symbol="AAPL",
        company_name="Apple Inc.",
        security_type="EQ",
        last_trade=Decimal("175.00"),
        bid=Decimal("174.95"),
        ask=Decimal("175.05"),
        change=Decimal("1.50"),
        change_pct=Decimal("0.86"),
        volume=50_000_000,
        bid_size=100,
        ask_size=200,
        high=Decimal("176.00"),
        low=Decimal("173.50"),
        open=Decimal("174.00"),
        close=Decimal("173.50"),
        high_52=Decimal("199.00"),
        low_52=Decimal("140.00"),
        pe_ratio=Decimal("28.5"),
        dividend=Decimal("0.96"),
        dividend_yield=Decimal("0.55"),
        market_cap=Decimal("2_750_000_000_000"),
        quote_status="REALTIME",
        timestamp="2024-01-15 16:00:00 EST",
    )


@pytest.fixture
async def mcp_client() -> AsyncGenerator[Client[FastMCPTransport], None]:
    """MCP client for testing server tools."""
    async with fastmcp.Client(server.mcp) as client:
        yield client


@pytest.fixture
def mock_repository_context(
    sample_account: Account,
    sample_balance: Balance,
    sample_portfolio: Portfolio,
    sample_quote: Quote,
) -> Generator[MagicMock, None, None]:
    """Mock the repository at the module level to prevent OAuth during tests."""
    mock_repo = MagicMock(spec=ETradeRepository)
    mock_repo.get_accounts.return_value = [sample_account]
    mock_repo.get_account_balance.return_value = sample_balance
    mock_repo.get_account_portfolio.return_value = sample_portfolio
    mock_repo.get_quotes.return_value = [sample_quote]
    mock_repo._is_authorized = True

    # Patch the _repositories dict with a dict containing our mock repo
    with patch("server._repositories", {"0": mock_repo}):
        yield mock_repo
