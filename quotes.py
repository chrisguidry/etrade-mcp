"""
Quotes: E*TRADE's market data for stocks, ETFs, mutual funds, and options.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from decimal import Decimal
from typing import Annotated, Any

from fastmcp.dependencies import Shared
from fastmcp.tools import tool
from pydantic import BaseModel, Field

from effects import READ, READS
from etrade_json import as_list, decimal_at
from profiles import Profiles, configured_profiles
from repository import ETradeRepository

logger = logging.getLogger(__name__)

# E*TRADE answers a quote request for at most this many symbols.
MAXIMUM_SYMBOLS = 25


class Quote(BaseModel):
    """Real-time or delayed quote for a security.

    Provides current pricing and trading information.
    """

    symbol: str = Field(..., description="Security symbol")
    company_name: str | None = Field(default=None, description="Company/security name")
    security_type: str | None = Field(
        default=None, description="Security type (e.g., 'EQ' for equity)"
    )

    # Current pricing
    last_trade: Decimal | None = Field(default=None, description="Last trade price")
    bid: Decimal | None = Field(default=None, description="Current bid price")
    ask: Decimal | None = Field(default=None, description="Current ask price")

    # Change metrics
    change: Decimal | None = Field(
        default=None, description="Change from previous close in dollars"
    )
    change_pct: Decimal | None = Field(
        default=None, description="Change from previous close as percentage"
    )

    # Volume and trading
    volume: int | None = Field(default=None, description="Trading volume for the day")
    bid_size: int | None = Field(default=None, description="Number of shares at bid")
    ask_size: int | None = Field(default=None, description="Number of shares at ask")

    # Price ranges
    high: Decimal | None = Field(default=None, description="Day's high price")
    low: Decimal | None = Field(default=None, description="Day's low price")
    open: Decimal | None = Field(default=None, description="Opening price")
    close: Decimal | None = Field(default=None, description="Previous closing price")
    high_52: Decimal | None = Field(default=None, description="52-week high")
    low_52: Decimal | None = Field(default=None, description="52-week low")

    # Additional data
    pe_ratio: Decimal | None = Field(
        default=None, description="Price-to-earnings ratio"
    )
    dividend: Decimal | None = Field(
        default=None, description="Cash amount per share of the latest dividend"
    )
    dividend_yield: Decimal | None = Field(
        default=None, description="Dividend yield percentage"
    )
    market_cap: Decimal | None = Field(
        default=None, description="Market capitalization"
    )

    # Metadata
    quote_status: str | None = Field(
        default=None,
        description="Quote status: 'REALTIME', 'DELAYED', 'CLOSING', or an "
        "extended-hours status such as 'EH_REALTIME'",
    )
    timestamp: str | None = Field(default=None, description="Quote timestamp")

    @classmethod
    def from_etrade(cls, quote: dict[str, Any]) -> Quote:
        """Convert one quote from E*TRADE's quote response."""
        product = quote.get("Product", {})
        details = quote.get("All", {})
        return cls(
            symbol=product.get("symbol", ""),
            company_name=details.get("companyName") or product.get("companyName"),
            security_type=product.get("securityType"),
            last_trade=decimal_at(details, "lastTrade"),
            bid=decimal_at(details, "bid"),
            ask=decimal_at(details, "ask"),
            change=decimal_at(details, "changeClose"),
            change_pct=decimal_at(details, "changeClosePercentage"),
            volume=details.get("totalVolume"),
            bid_size=details.get("bidSize"),
            ask_size=details.get("askSize"),
            high=decimal_at(details, "high"),
            low=decimal_at(details, "low"),
            open=decimal_at(details, "open"),
            close=decimal_at(details, "previousClose"),
            high_52=decimal_at(details, "high52"),
            low_52=decimal_at(details, "low52"),
            pe_ratio=decimal_at(details, "pe"),
            dividend=decimal_at(details, "dividend"),
            dividend_yield=decimal_at(details, "yield"),
            market_cap=decimal_at(details, "marketCap"),
            quote_status=quote.get("quoteStatus"),
            timestamp=quote.get("dateTime"),
        )


class QuotesResponse(BaseModel):
    """Response containing quotes for one or more securities."""

    quotes: list[Quote] = Field(
        default_factory=list, description="List of security quotes"
    )
    messages: list[str] = Field(
        default_factory=list,
        description="E*TRADE's messages about the request, such as a symbol it "
        "does not recognize",
    )


def fetch_quotes(repository: ETradeRepository, symbols: list[str]) -> QuotesResponse:
    """Fetch quotes for up to 25 symbols in one request."""
    if not symbols:
        return QuotesResponse()

    logger.info(f"Fetching quotes for {len(symbols)} symbols")
    data = repository.get(f"/v1/market/quote/{','.join(symbols)}.json")
    response = data.get("QuoteResponse", {})
    return QuotesResponse(
        quotes=[
            Quote.from_etrade(quote) for quote in as_list(response.get("QuoteData"))
        ],
        messages=[
            message.get("description", "")
            for message in as_list(response.get("Messages", {}).get("Message"))
        ],
    )


@tool(title="Get quotes", tags={"quotes", READ}, annotations=READS)
def get_quotes(
    symbols: Annotated[list[str], Field(max_length=MAXIMUM_SYMBOLS)],
    profile: str = "0",
    profiles: Profiles = Shared(configured_profiles),
) -> QuotesResponse:
    """Get real-time or delayed quotes for one or more securities.

    Works for stocks, ETFs, mutual funds, and other securities.  Each quote has
    the last trade, bid, and ask, the change from the previous close in
    dollars and percent, the day's volume and range, the 52-week range, and the
    P/E ratio, dividend, yield, and market cap.  Prices are in USD.

    A quote may be real-time or delayed by 15 minutes, depending on the E*TRADE
    account and the exchange.  quote_status says which.  When E*TRADE does not
    recognize a symbol, it has no quote and messages says why.

    Args:
        symbols: Ticker symbols to quote, at most 25 (e.g., ["AAPL", "SPY"])
            (required)
        profile: Profile ID from list_profiles whose E*TRADE access to use
            (default: "0")

    Returns:
        QuotesResponse with a quote for each symbol E*TRADE recognizes, and
        E*TRADE's messages about the others
    """
    return fetch_quotes(profiles.repository(profile), symbols)


TOOLS: list[Callable[..., object]] = [get_quotes]
