"""
The E*TRADE MCP server: one FastMCP server with every domain's tools.

Every tool only reads.  None of them places, changes, or cancels an order, or
moves money.
"""

import logging

from fastmcp import FastMCP

import accounts
import portfolios
import profiles
import quotes
import transactions
from etrade_errors import ETradeErrorMiddleware

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

INSTRUCTIONS = """
Gives you read-only access to the user's E*TRADE brokerage and bank accounts:
the accounts, their balances, the positions in each portfolio, each brokerage
account's transactions, and market quotes.  Use it to answer questions about
investment performance, asset allocation, cash available to invest, recent
trades, dividends, and transfers, and the price of a security.  It cannot
place, change, or cancel orders, and it cannot move money.

Start with list_accounts.  Pass an account's account_id_key to
get_account_balance, get_account_portfolio, and get_transactions.

The server can hold several E*TRADE logins, called profiles, such as one per
household member.  Every tool takes a profile argument, which defaults to "0".
When the user has more than one login, call list_profiles first, and look in
every profile's accounts.

All amounts are in USD.  Percentages are in percent, so 2.5 means 2.5%.  A short
position has a negative quantity and market value.  Quotes may be delayed by up
to 15 minutes; each quote's quote_status says whether it is real-time.
"""

mcp: FastMCP[None] = FastMCP(
    name="E*TRADE",
    instructions=INSTRUCTIONS,
    middleware=[ETradeErrorMiddleware()],
    mask_error_details=True,
    tools=[
        *profiles.TOOLS,
        *accounts.TOOLS,
        *portfolios.TOOLS,
        *transactions.TOOLS,
        *quotes.TOOLS,
    ],
)


if __name__ == "__main__":
    # Authorize every profile before serving.  The tokens are stored, so the
    # server's own repositories load them on first use.
    for repository in profiles.create_repositories_from_env().values():
        repository.authorize()

    mcp.run()
