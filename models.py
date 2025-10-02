"""
Pydantic models for E*TRADE MCP Server responses.

These models provide structured data types for E*TRADE API responses,
focused on read-only account and investment information.
"""

from decimal import Decimal

from pydantic import BaseModel, Field


class Account(BaseModel):
    """An E*TRADE account with basic information.

    Represents a brokerage or bank account without detailed balance information.
    Use get_account_balance() for detailed financial information.
    """

    account_id: str = Field(..., description="Unique account identifier")
    account_id_key: str = Field(
        ..., description="Encrypted account identifier for API calls"
    )
    account_mode: str = Field(
        ...,
        description="Account mode. Common values: 'CASH', 'MARGIN', 'IRA'",
    )
    account_desc: str = Field(..., description="Account description/nickname")
    account_name: str | None = Field(
        None, description="Account name if different from description"
    )
    account_type: str = Field(
        ...,
        description="Account type. Common values: 'INDIVIDUAL', 'JOINT', 'IRA', etc.",
    )
    institution_type: str = Field(
        ..., description="Institution type: 'BROKERAGE' or 'BANK'"
    )
    account_status: str = Field(..., description="Account status: 'ACTIVE' or 'CLOSED'")
    closed_date: int | None = Field(None, description="Closed date as Unix timestamp")
    profile_id: str = Field(..., description="Profile identifier for this account")
    profile_label: str | None = Field(
        None, description="Human-readable label for this profile"
    )


class Balance(BaseModel):
    """Detailed balance information for an E*TRADE account.

    All monetary amounts are in USD with Decimal precision.
    """

    account_id: str = Field(..., description="Account identifier")
    account_type: str = Field(..., description="Account type")
    account_description: str | None = Field(None, description="Account description")
    account_mode: str | None = Field(None, description="Account mode")

    # Cash balances
    cash_balance: Decimal | None = Field(
        None, description="Current cash balance available"
    )
    cash_buying_power: Decimal | None = Field(
        None, description="Cash available for purchases"
    )
    margin_buying_power: Decimal | None = Field(
        None, description="Margin buying power (for margin accounts)"
    )

    # Account value
    total_account_value: Decimal | None = Field(
        None, description="Total account value including all positions"
    )
    net_account_value: Decimal | None = Field(
        None, description="Net account value (assets - liabilities)"
    )

    # Additional fields for brokerage accounts
    uncleared_deposits: Decimal | None = Field(
        None, description="Deposits not yet cleared"
    )
    funds_withheld_from_purchase_power: Decimal | None = Field(
        None, description="Funds held and unavailable for trading"
    )
    funds_withheld_from_withdrawal: Decimal | None = Field(
        None, description="Funds held and unavailable for withdrawal"
    )

    # Profile information
    profile_id: str = Field(..., description="Profile identifier for this account")
    profile_label: str | None = Field(
        None, description="Human-readable label for this profile"
    )


class Position(BaseModel):
    """A single position (holding) in a brokerage account.

    Represents ownership of a security with current valuation.
    """

    symbol: str = Field(..., description="Security symbol (e.g., 'AAPL', 'SPY')")
    symbol_description: str = Field(
        ..., description="Human-readable security name/description"
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
        None, description="Current market value of position"
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
    quote_detail: str | None = Field(
        None, description="Quote detail level used for valuation"
    )


class Portfolio(BaseModel):
    """Portfolio holdings for an account.

    Contains all positions (holdings) in the account with current valuations.
    """

    account_id: str = Field(..., description="Account identifier")
    positions: list[Position] = Field(
        default_factory=list, description="List of positions in the account"
    )
    total_market_value: Decimal | None = Field(
        None, description="Total market value of all positions"
    )
    profile_id: str = Field(..., description="Profile identifier for this account")
    profile_label: str | None = Field(
        None, description="Human-readable label for this profile"
    )


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
        default=None, description="Annual dividend per share"
    )
    dividend_yield: Decimal | None = Field(
        default=None, description="Dividend yield percentage"
    )
    market_cap: Decimal | None = Field(
        default=None, description="Market capitalization"
    )

    # Metadata
    quote_status: str | None = Field(
        default=None, description="Quote status (e.g., 'REALTIME', 'DELAYED')"
    )
    timestamp: str | None = Field(default=None, description="Quote timestamp")


class AccountsResponse(BaseModel):
    """Response containing a list of accounts."""

    accounts: list[Account] = Field(
        default_factory=list, description="List of E*TRADE accounts"
    )


class QuotesResponse(BaseModel):
    """Response containing quotes for one or more securities."""

    quotes: list[Quote] = Field(
        default_factory=list, description="List of security quotes"
    )
