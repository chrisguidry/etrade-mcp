"""
Test getting market quotes.
"""

from typing import Any

import pytest
from conftest import FakeETrade
from fastmcp.client import Client, FastMCPTransport
from fastmcp.exceptions import ToolError


def quote_json(symbol: str, **details: Any) -> dict[str, Any]:
    """One quote from E*TRADE's quote response."""
    return {
        "dateTime": "16:00:00 EDT 10-21-2026",
        "quoteStatus": "CLOSING",
        "Product": {"symbol": symbol, "securityType": "EQ"},
        "All": details,
    }


async def get_quotes(
    mcp_client: Client[FastMCPTransport], symbols: list[str]
) -> dict[str, Any]:
    result = await mcp_client.call_tool("get_quotes", {"symbols": symbols})
    assert result.structured_content is not None
    return result.structured_content


async def test_get_quotes(
    etrade: FakeETrade, mcp_client: Client[FastMCPTransport]
) -> None:
    etrade.answer(
        "/v1/market/quote/AAPL.json",
        {
            "QuoteResponse": {
                "QuoteData": quote_json(
                    "AAPL",
                    companyName="APPLE INC COM",
                    lastTrade=175.0,
                    bid=174.95,
                    ask=175.05,
                    bidSize=100,
                    askSize=200,
                    changeClose=1.5,
                    changeClosePercentage=0.86,
                    totalVolume=50_000_000,
                    high=176.0,
                    low=173.5,
                    open=174.0,
                    previousClose=173.5,
                    high52=199.0,
                    low52=140.0,
                    pe=28.5,
                    dividend=0.26,
                    marketCap=2_750_000_000_000,
                    **{"yield": 0.55},
                )
            }
        },
    )

    quotes = await get_quotes(mcp_client, ["AAPL"])

    assert quotes == {
        "quotes": [
            {
                "symbol": "AAPL",
                "company_name": "APPLE INC COM",
                "security_type": "EQ",
                "last_trade": "175.0",
                "bid": "174.95",
                "ask": "175.05",
                "change": "1.5",
                "change_pct": "0.86",
                "volume": 50_000_000,
                "bid_size": 100,
                "ask_size": 200,
                "high": "176.0",
                "low": "173.5",
                "open": "174.0",
                "close": "173.5",
                "high_52": "199.0",
                "low_52": "140.0",
                "pe_ratio": "28.5",
                "dividend": "0.26",
                "dividend_yield": "0.55",
                "market_cap": "2750000000000",
                "quote_status": "CLOSING",
                "timestamp": "16:00:00 EDT 10-21-2026",
            }
        ],
        "messages": [],
    }


async def test_get_quotes_for_several_symbols(
    etrade: FakeETrade, mcp_client: Client[FastMCPTransport]
) -> None:
    etrade.answer(
        "/v1/market/quote/AAPL,MSFT.json",
        {
            "QuoteResponse": {
                "QuoteData": [
                    quote_json("AAPL", lastTrade=175.0),
                    quote_json("MSFT", lastTrade=380.0),
                ]
            }
        },
    )

    quotes = await get_quotes(mcp_client, ["AAPL", "MSFT"])

    prices = {quote["symbol"]: quote["last_trade"] for quote in quotes["quotes"]}
    assert prices == {"AAPL": "175.0", "MSFT": "380.0"}


async def test_get_quotes_reports_symbols_etrade_does_not_recognize(
    etrade: FakeETrade, mcp_client: Client[FastMCPTransport]
) -> None:
    etrade.answer(
        "/v1/market/quote/AAPL,APPL.json",
        {
            "QuoteResponse": {
                "QuoteData": quote_json("AAPL", lastTrade=175.0),
                "Messages": {
                    "Message": {
                        "description": "APPL is not a valid symbol",
                        "code": 1019,
                        "type": "WARNING",
                    }
                },
            }
        },
    )

    quotes = await get_quotes(mcp_client, ["AAPL", "APPL"])

    assert [quote["symbol"] for quote in quotes["quotes"]] == ["AAPL"]
    assert quotes["messages"] == ["APPL is not a valid symbol"]


async def test_get_quotes_for_no_symbols(
    etrade: FakeETrade, mcp_client: Client[FastMCPTransport]
) -> None:
    quotes = await get_quotes(mcp_client, [])

    assert quotes == {"quotes": [], "messages": []}
    assert etrade.requests == []


async def test_get_quotes_rejects_more_than_25_symbols(
    etrade: FakeETrade, mcp_client: Client[FastMCPTransport]
) -> None:
    symbols = [f"SYM{i}" for i in range(26)]

    with pytest.raises(ToolError, match="at most 25 items"):
        await mcp_client.call_tool("get_quotes", {"symbols": symbols})

    assert etrade.requests == []
