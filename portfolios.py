"""
Portfolios: the positions held in each brokerage account, and their value.

E*TRADE returns a portfolio in pages of 50 positions, so this reads every page
before it totals the portfolio.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import date
from decimal import Decimal
from typing import Any

from fastmcp.dependencies import Shared
from fastmcp.tools import tool
from pydantic import BaseModel, Field

from effects import READ, READS
from etrade_json import as_list, decimal_at
from pagination import PaginationInfo, paginate
from profiles import Profiles, configured_profiles
from repository import ETradeRepository

logger = logging.getLogger(__name__)

# A limit on the pages read, so that a wrong page count cannot make the server
# send requests without end.  At 50 positions a page, this is 5,000 positions.
MAXIMUM_PAGES = 100


class Position(BaseModel):
    """A single position (holding) in a brokerage account.

    Represents ownership of a security with current valuation.
    """

    symbol: str = Field(
        ...,
        description="Security symbol (e.g., 'AAPL', 'SPY').  For an option, the "
        "underlying security's symbol",
    )
    symbol_description: str = Field(
        ...,
        description="E*TRADE's description of the security.  For a stock, its "
        "symbol; for an option, its symbol, expiry, strike, and type",
    )
    type_code: str = Field(
        ...,
        description="Security type code. Common values: 'EQ' (equity/stock), "
        "'MF' (mutual fund), 'OPTN' (option)",
    )
    quantity: Decimal = Field(..., description="Number of shares/units held")

    # Cost basis
    price_paid: Decimal | None = Field(None, description="Average price paid per share")
    total_cost: Decimal | None = Field(None, description="Total cost basis of position")
    cost_per_share: Decimal | None = Field(
        None, description="Cost per share (may differ from price_paid)"
    )

    # Current value
    last_trade: Decimal | None = Field(None, description="Last trade price")
    market_value: Decimal | None = Field(
        None,
        description="Current market value of position.  Negative for a short position",
    )

    # Performance
    total_gain: Decimal | None = Field(
        None, description="Total gain/loss in dollars (market_value - total_cost)"
    )
    total_gain_pct: Decimal | None = Field(
        None, description="Total gain/loss as percentage"
    )
    days_gain: Decimal | None = Field(None, description="Change in value today")
    days_gain_pct: Decimal | None = Field(None, description="Percentage change today")

    # Additional position details
    position_type: str | None = Field(
        None, description="Position type: 'LONG' or 'SHORT'"
    )

    # Option contract, null for any other security
    call_put: str | None = Field(
        None, description="For an option, 'CALL' or 'PUT'.  Null for other securities"
    )
    strike_price: Decimal | None = Field(
        None, description="For an option, the strike price.  Null for other securities"
    )
    expiry_date: date | None = Field(
        None,
        description="For an option, the date it expires.  Null for other securities",
    )

    @classmethod
    def from_etrade(cls, position: dict[str, Any]) -> Position:
        """Convert one position from E*TRADE's portfolio response."""
        product = position.get("Product", {})
        description = position.get("symbolDescription", "")
        option = product if product.get("securityType") == "OPTN" else {}
        return cls(
            symbol=product.get("symbol") or description,
            symbol_description=description,
            type_code=product.get("securityType", ""),
            quantity=Decimal(str(position.get("quantity", 0))),
            price_paid=decimal_at(position, "pricePaid"),
            total_cost=decimal_at(position, "totalCost"),
            cost_per_share=decimal_at(position, "costPerShare"),
            last_trade=decimal_at(position.get("Quick", {}), "lastTrade"),
            market_value=decimal_at(position, "marketValue"),
            total_gain=decimal_at(position, "totalGain"),
            total_gain_pct=decimal_at(position, "totalGainPct"),
            days_gain=decimal_at(position, "daysGain"),
            days_gain_pct=decimal_at(position, "daysGainPct"),
            position_type=position.get("positionType"),
            call_put=option.get("callPut"),
            strike_price=decimal_at(option, "strikePrice"),
            expiry_date=option_expiry(option),
        )


def option_expiry(product: dict[str, Any]) -> date | None:
    """The date an option expires, from its product's year, month, and day.

    E*TRADE sends zeros for a security that does not expire, which is no date.
    """
    try:
        return date(
            int(product["expiryYear"]),
            int(product["expiryMonth"]),
            int(product["expiryDay"]),
        )
    except (KeyError, TypeError, ValueError):
        return None


def page_count(portfolios: list[dict[str, Any]]) -> int:
    """The number of pages in the portfolio, which is 1 when E*TRADE omits it.

    E*TRADE documents this as totalNoOfPages, but its sample responses name it
    totalPages, so this reads either.
    """
    counts = [
        int(str(count))
        for portfolio in portfolios
        for key in ("totalPages", "totalNoOfPages")
        if str(count := portfolio.get(key)).isdigit()
    ]
    return max(counts, default=1)


def fetch_positions(
    repository: ETradeRepository, account_id_key: str
) -> list[Position]:
    """Fetch every position in an account, reading each page of the portfolio."""
    logger.info("Fetching account portfolio")
    positions: list[Position] = []
    page = 1
    last_page = 1
    while page <= last_page:
        data = repository.get(
            f"/v1/accounts/{account_id_key}/portfolio.json",
            params={"pageNumber": str(page)},
        )
        portfolios = as_list(data.get("PortfolioResponse", {}).get("AccountPortfolio"))
        positions.extend(
            Position.from_etrade(position)
            for portfolio in portfolios
            for position in as_list(portfolio.get("Position"))
        )
        last_page = min(page_count(portfolios), MAXIMUM_PAGES)
        page += 1
    return positions


class Portfolio(BaseModel):
    """One page of an account's positions, and the value of all of them."""

    account_id: str = Field(..., description="Account identifier")
    positions: list[Position] = Field(
        default_factory=list,
        description="One page of the positions in the account",
    )
    total_market_value: Decimal | None = Field(
        None,
        description="Total market value of every position in the account, on "
        "every page.  Null when no position has a market value",
    )
    profile_id: str = Field(..., description="Profile identifier for this account")
    profile_label: str | None = Field(
        None, description="Human-readable label for this profile"
    )
    pagination: PaginationInfo = Field(..., description="Pagination information")


def total_market_value(positions: list[Position]) -> Decimal | None:
    """The sum of the positions' market values, counting short positions as
    negative, or None when no position has a market value."""
    values = [p.market_value for p in positions if p.market_value is not None]
    return sum(values, Decimal(0)) if values else None


@tool(title="Get account portfolio", tags={"portfolios", READ}, annotations=READS)
def get_account_portfolio(
    account_id_key: str,
    profile: str = "0",
    limit: int = 100,
    offset: int = 0,
    profiles: Profiles = Shared(configured_profiles),
) -> Portfolio:
    """Get the positions held in one account, with their value and gains.

    Each position has its symbol, security type, quantity, cost basis, current
    market value, and total and daily gain or loss.  Amounts are in USD, and
    percentages are in percent (16.67 means 16.67%).

    total_market_value covers every position in the account, not only the
    page returned.

    Args:
        account_id_key: The account's account_id_key from list_accounts (required)
        profile: Profile ID from list_profiles that owns the account
            (default: "0")
        limit: Maximum number of positions to return (default: 100)
        offset: Number of positions to skip, for the next page (default: 0)

    Returns:
        Portfolio with one page of positions, the total market value, and
        pagination information
    """
    repository = profiles.repository(profile)
    positions = fetch_positions(repository, account_id_key)
    page, pagination = paginate(positions, limit, offset)
    return Portfolio(
        account_id=account_id_key,
        positions=page,
        total_market_value=total_market_value(positions),
        profile_id=repository.profile_id,
        profile_label=repository.profile_label,
        pagination=pagination,
    )


TOOLS: list[Callable[..., object]] = [get_account_portfolio]
