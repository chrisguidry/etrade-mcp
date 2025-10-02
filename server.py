"""
E*TRADE MCP Server.

Provides MCP tools for accessing E*TRADE account information, balances, portfolios,
and market quotes.
"""

import logging

from fastmcp import FastMCP

from models import AccountsResponse, Balance, Portfolio, QuotesResponse
from repository import ETradeRepository, create_repositories_from_env

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

mcp = FastMCP[None](
    name="E*TRADE",
    instructions="""
    Provides access to E*TRADE brokerage and bank accounts, including account
    information, balances, portfolio holdings, and market quotes.

    This server is designed for personal finance management and investment tracking,
    not for active trading. It provides read-only access to help users understand
    their investment performance and asset allocation.

    Key capabilities:
    - List all E*TRADE accounts
    - Get detailed balance information for accounts
    - View portfolio holdings with current valuations
    - Get real-time or delayed quotes for securities

    The server works with both E*TRADE sandbox (for testing) and production
    environments, configured via the ETRADE_ENVIRONMENT environment variable.
    """,
)

# Module-level repository instances (one per profile)
_repositories: dict[str, ETradeRepository] = {}


def get_repository(profile_id: str = "0") -> ETradeRepository:
    """Get or create the E*TRADE repository instance for a specific profile.

    Args:
        profile_id: Profile identifier (default: "0")

    Returns:
        ETradeRepository instance for the specified profile
    """
    global _repositories

    if not _repositories:
        # Initialize all repositories from environment
        _repositories = create_repositories_from_env()

        # Perform OAuth authorization for all profiles
        for repo in _repositories.values():
            if not repo._is_authorized:
                repo.authorize()

    if profile_id not in _repositories:
        raise ValueError(
            f"Profile {profile_id} not found. "
            f"Available profiles: {', '.join(sorted(_repositories.keys()))}"
        )

    return _repositories[profile_id]


@mcp.tool()
def list_accounts(profile: str = "0") -> AccountsResponse:
    """List all E*TRADE accounts for a specific profile.

    Returns all active accounts (brokerage and bank) associated with the
    authenticated user. Closed accounts are automatically excluded.

    Each account includes:
    - Account ID and encrypted key for API calls
    - Account description/nickname
    - Account type (INDIVIDUAL, JOINT, IRA, etc.)
    - Account mode (CASH, MARGIN, IRA)
    - Institution type (BROKERAGE or BANK)
    - Account status
    - Profile ID and label

    Use the account_id_key field from the returned accounts when calling
    other tools like get_account_balance() or get_account_portfolio().

    Args:
        profile: Profile identifier (default: "0")

    Returns:
        AccountsResponse with list of active accounts for this profile
    """
    accounts = get_repository(profile).get_accounts()
    return AccountsResponse(accounts=accounts)


@mcp.tool()
def get_account_balance(account_id_key: str, profile: str = "0") -> Balance:
    """Get detailed balance information for a specific account.

    Provides comprehensive balance information including:
    - Cash balances and buying power
    - Total account value (real-time or delayed)
    - Margin information (for margin accounts)
    - Pending deposits and holds

    Args:
        account_id_key: Account identifier key from list_accounts()
                       (use account.account_id_key field)
        profile: Profile identifier (default: "0")

    Returns:
        Balance object with detailed account balance information
    """
    return get_repository(profile).get_account_balance(account_id_key)


@mcp.tool()
def get_account_portfolio(account_id_key: str, profile: str = "0") -> Portfolio:
    """Get portfolio holdings for a specific account.

    Returns all positions (holdings) in the account with current valuations,
    cost basis, and performance metrics.

    Each position includes:
    - Security symbol and description
    - Quantity held
    - Cost basis (price paid, total cost)
    - Current market value
    - Gains/losses (total and daily)
    - Position type (LONG/SHORT)

    Args:
        account_id_key: Account identifier key from list_accounts()
                       (use account.account_id_key field)
        profile: Profile identifier (default: "0")

    Returns:
        Portfolio object with all positions and total market value
    """
    return get_repository(profile).get_account_portfolio(account_id_key)


@mcp.tool()
def get_quotes(symbols: list[str], profile: str = "0") -> QuotesResponse:
    """Get real-time or delayed quotes for one or more securities.

    Provides current market data for stocks, ETFs, mutual funds, and other
    securities. Quotes may be real-time or delayed by 15 minutes depending
    on E*TRADE account type and exchange.

    Each quote includes:
    - Current pricing (last trade, bid, ask)
    - Price changes (dollar and percentage)
    - Trading volume
    - Price ranges (daily and 52-week)
    - Fundamental data (P/E ratio, dividend, market cap)

    Args:
        symbols: List of ticker symbols to get quotes for (e.g., ["AAPL", "SPY"])
                Maximum 25 symbols per request
        profile: Profile identifier to use for API access (default: "0")

    Returns:
        QuotesResponse with quotes for all requested symbols

    Example:
        get_quotes(["AAPL", "MSFT", "GOOGL"])
    """
    if len(symbols) > 25:
        raise ValueError("Maximum 25 symbols allowed per request")

    quotes = get_repository(profile).get_quotes(symbols)
    return QuotesResponse(quotes=quotes)


if __name__ == "__main__":
    # Initialize repository at startup
    get_repository()

    # Run the MCP server
    mcp.run()
