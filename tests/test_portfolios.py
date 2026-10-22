"""
Test reading an account's portfolio.
"""

from decimal import Decimal
from typing import Any

import pytest
from conftest import FakeETrade
from fastmcp.client import Client, FastMCPTransport

from portfolios import MAXIMUM_PAGES, page_count

PORTFOLIO = "/v1/accounts/abc123xyz/portfolio.json"


def position_json(
    symbol: str = "AAPL",
    market_value: float | None = 1750.0,
    **fields: Any,
) -> dict[str, Any]:
    """One position from E*TRADE's portfolio response."""
    position: dict[str, Any] = {
        "symbolDescription": symbol,
        "quantity": 10,
        "positionType": "LONG",
        "Product": {"symbol": symbol, "securityType": "EQ"},
        "Quick": {"lastTrade": 175.0},
        **fields,
    }
    if market_value is not None:
        position["marketValue"] = market_value
    return position


def portfolio_json(*positions: dict[str, Any], **fields: Any) -> dict[str, Any]:
    """E*TRADE's portfolio response.  One position arrives as a bare object."""
    listed: Any = positions[0] if len(positions) == 1 else list(positions)
    return {"PortfolioResponse": {"AccountPortfolio": {"Position": listed, **fields}}}


async def get_portfolio(
    mcp_client: Client[FastMCPTransport], **arguments: Any
) -> dict[str, Any]:
    result = await mcp_client.call_tool(
        "get_account_portfolio", {"account_id_key": "abc123xyz", **arguments}
    )
    assert result.structured_content is not None
    return result.structured_content


async def test_get_account_portfolio(
    etrade: FakeETrade, mcp_client: Client[FastMCPTransport]
) -> None:
    etrade.answer(
        PORTFOLIO,
        portfolio_json(
            position_json(
                pricePaid=150.0,
                totalCost=1500.0,
                costPerShare=150.0,
                totalGain=250.0,
                totalGainPct=16.67,
                daysGain=10.0,
                daysGainPct=0.57,
            )
        ),
    )

    portfolio = await get_portfolio(mcp_client)

    assert portfolio == {
        "account_id": "abc123xyz",
        "positions": [
            {
                "symbol": "AAPL",
                "symbol_description": "AAPL",
                "type_code": "EQ",
                "quantity": "10",
                "price_paid": "150.0",
                "total_cost": "1500.0",
                "cost_per_share": "150.0",
                "last_trade": "175.0",
                "market_value": "1750.0",
                "total_gain": "250.0",
                "total_gain_pct": "16.67",
                "days_gain": "10.0",
                "days_gain_pct": "0.57",
                "position_type": "LONG",
                "quote_detail": None,
            }
        ],
        "total_market_value": "1750.0",
        "profile_id": "0",
        "profile_label": None,
        "pagination": {"total_count": 1, "limit": 100, "offset": 0, "has_more": False},
    }


async def test_an_option_position_has_its_underlying_symbol(
    etrade: FakeETrade, mcp_client: Client[FastMCPTransport]
) -> None:
    option = position_json(
        symbolDescription="AAPL Jan 15 '27 $200 Call",
        Product={"symbol": "AAPL", "securityType": "OPTN"},
    )
    etrade.answer(PORTFOLIO, portfolio_json(option))

    portfolio = await get_portfolio(mcp_client)

    [position] = portfolio["positions"]
    assert position["symbol"] == "AAPL"
    assert position["symbol_description"] == "AAPL Jan 15 '27 $200 Call"
    assert position["type_code"] == "OPTN"


async def test_get_account_portfolio_reads_every_page(
    etrade: FakeETrade, mcp_client: Client[FastMCPTransport]
) -> None:
    etrade.answer(
        PORTFOLIO,
        portfolio_json(position_json("AAPL"), position_json("MSFT"), totalPages=2),
        params={"pageNumber": "1"},
    )
    etrade.answer(
        PORTFOLIO,
        portfolio_json(position_json("SPY"), totalPages=2),
        params={"pageNumber": "2"},
    )

    portfolio = await get_portfolio(mcp_client)

    symbols = [position["symbol"] for position in portfolio["positions"]]
    assert symbols == ["AAPL", "MSFT", "SPY"]
    assert portfolio["total_market_value"] == "5250.0"


async def test_get_account_portfolio_pages_positions(
    etrade: FakeETrade, mcp_client: Client[FastMCPTransport]
) -> None:
    etrade.answer(
        PORTFOLIO,
        portfolio_json(
            position_json("AAPL"), position_json("MSFT"), position_json("SPY")
        ),
    )

    portfolio = await get_portfolio(mcp_client, limit=1, offset=1)

    assert [position["symbol"] for position in portfolio["positions"]] == ["MSFT"]
    assert portfolio["total_market_value"] == "5250.0"
    assert portfolio["pagination"] == {
        "total_count": 3,
        "limit": 1,
        "offset": 1,
        "has_more": True,
    }


@pytest.mark.parametrize(
    ("market_values", "total"),
    [
        ([1750.0, -500.0], "1250.0"),
        ([-500.0], "-500.0"),
        ([1750.0, None], "1750.0"),
        ([None], None),
    ],
)
async def test_total_market_value(
    etrade: FakeETrade,
    mcp_client: Client[FastMCPTransport],
    market_values: list[float | None],
    total: str | None,
) -> None:
    positions = [position_json(market_value=value) for value in market_values]
    etrade.answer(PORTFOLIO, portfolio_json(*positions))

    portfolio = await get_portfolio(mcp_client)

    assert portfolio["total_market_value"] == total


async def test_an_empty_portfolio(
    etrade: FakeETrade, mcp_client: Client[FastMCPTransport]
) -> None:
    etrade.answer(PORTFOLIO, {"PortfolioResponse": {}})

    portfolio = await get_portfolio(mcp_client)

    assert portfolio["positions"] == []
    assert portfolio["total_market_value"] is None


@pytest.mark.parametrize(
    ("portfolios", "pages"),
    [
        ([], 1),
        ([{}], 1),
        ([{"totalPages": 3}], 3),
        ([{"totalNoOfPages": "4"}], 4),
        ([{"totalPages": "many"}], 1),
        ([{"totalPages": 2}, {"totalPages": 5}], 5),
    ],
)
def test_page_count(portfolios: list[dict[str, Any]], pages: int) -> None:
    assert page_count(portfolios) == pages


async def test_get_account_portfolio_reads_at_most_the_page_limit(
    etrade: FakeETrade, mcp_client: Client[FastMCPTransport]
) -> None:
    etrade.answer(PORTFOLIO, portfolio_json(position_json(), totalPages=1_000_000))

    portfolio = await get_portfolio(mcp_client)

    assert len(etrade.requests) == MAXIMUM_PAGES
    assert Decimal(portfolio["total_market_value"]) == 1750 * MAXIMUM_PAGES
