"""
Accounts: the user's E*TRADE brokerage and bank accounts, and their balances.

Every other account tool takes an account's account_id_key, which E*TRADE
issues in place of the account number.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from decimal import Decimal
from typing import Any

from fastmcp.dependencies import Shared
from fastmcp.exceptions import ToolError
from fastmcp.tools import tool
from pydantic import BaseModel, Field

from effects import READ, READS
from etrade_json import as_list, decimal_at
from pagination import PaginationInfo, paginate
from profiles import Profiles, configured_profiles
from repository import ETradeRepository

logger = logging.getLogger(__name__)


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

    @classmethod
    def from_etrade(
        cls, account: dict[str, Any], repository: ETradeRepository
    ) -> Account:
        """Convert one account from E*TRADE's account list."""
        return cls(
            account_id=account.get("accountId", ""),
            account_id_key=account.get("accountIdKey", ""),
            account_mode=account.get("accountMode", ""),
            account_desc=account.get("accountDesc", ""),
            account_name=account.get("accountName"),
            account_type=account.get("accountType", ""),
            institution_type=account.get("institutionType", ""),
            account_status=account.get("accountStatus", ""),
            closed_date=account.get("closedDate"),
            profile_id=repository.profile_id,
            profile_label=repository.profile_label,
        )


def fetch_accounts(repository: ETradeRepository) -> list[Account]:
    """Fetch the profile's accounts, leaving out closed ones."""
    logger.info("Fetching account list")
    data = repository.get("/v1/accounts/list.json")
    accounts = as_list(
        data.get("AccountListResponse", {}).get("Accounts", {}).get("Account")
    )
    return [
        Account.from_etrade(account, repository)
        for account in accounts
        if account.get("accountStatus") != "CLOSED"
    ]


class AccountsResponse(BaseModel):
    """Response containing a list of accounts."""

    accounts: list[Account] = Field(
        default_factory=list, description="List of E*TRADE accounts"
    )
    pagination: PaginationInfo = Field(..., description="Pagination information")


@tool(title="List accounts", tags={"accounts", READ}, annotations=READS)
def list_accounts(
    profile: str = "0",
    limit: int = 100,
    offset: int = 0,
    profiles: Profiles = Shared(configured_profiles),
) -> AccountsResponse:
    """List the open E*TRADE accounts for one profile.

    Returns brokerage and bank accounts.  Closed accounts are left out.  Each
    account has its type (INDIVIDUAL, JOINT, IRA, and others), its mode (CASH,
    MARGIN, or IRA), and its institution type (BROKERAGE or BANK).

    Pass an account's account_id_key to get_account_balance,
    get_account_portfolio, and get_transactions.

    Args:
        profile: Profile ID from list_profiles (default: "0")
        limit: Maximum number of accounts to return (default: 100)
        offset: Number of accounts to skip, for the next page (default: 0)

    Returns:
        AccountsResponse with one page of accounts and pagination information
    """
    accounts = fetch_accounts(profiles.repository(profile))
    page, pagination = paginate(accounts, limit, offset)
    return AccountsResponse(accounts=page, pagination=pagination)


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
    cash_available_for_investment: Decimal | None = Field(
        None, description="Cash available to invest"
    )
    cash_available_for_withdrawal: Decimal | None = Field(
        None, description="Cash available to withdraw"
    )
    settled_cash_for_investment: Decimal | None = Field(
        None, description="Settled cash available to invest"
    )
    unsettled_cash_for_investment: Decimal | None = Field(
        None, description="Cash available to invest that has not settled yet"
    )
    net_cash: Decimal | None = Field(None, description="Net cash balance")
    money_market_balance: Decimal | None = Field(
        None,
        description="Balance of the account's money market or sweep deposit account",
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

    @classmethod
    def from_etrade(
        cls, balance: dict[str, Any], repository: ETradeRepository
    ) -> Balance:
        """Convert E*TRADE's balance response."""
        computed = balance.get("Computed", {})
        cash = balance.get("Cash", {})
        realtime_values = computed.get("RealTimeValues", {})
        return cls(
            account_id=balance.get("accountId", ""),
            account_type=balance.get("accountType", ""),
            account_description=balance.get("accountDescription"),
            account_mode=balance.get("accountMode"),
            cash_balance=decimal_at(computed, "cashBalance"),
            cash_buying_power=decimal_at(computed, "cashBuyingPower"),
            margin_buying_power=decimal_at(computed, "marginBuyingPower"),
            cash_available_for_investment=decimal_at(
                computed, "cashAvailableForInvestment"
            ),
            cash_available_for_withdrawal=decimal_at(
                computed, "cashAvailableForWithdrawal"
            ),
            settled_cash_for_investment=decimal_at(
                computed, "settledCashForInvestment"
            ),
            unsettled_cash_for_investment=decimal_at(
                computed, "unSettledCashForInvestment"
            ),
            net_cash=decimal_at(computed, "netCash"),
            money_market_balance=decimal_at(cash, "moneyMktBalance"),
            total_account_value=decimal_at(realtime_values, "totalAccountValue"),
            net_account_value=decimal_at(realtime_values, "netAccountValue"),
            uncleared_deposits=decimal_at(computed, "unclearedDeposits"),
            funds_withheld_from_purchase_power=decimal_at(
                computed, "fundsWithheldFromPurchasePower"
            ),
            funds_withheld_from_withdrawal=decimal_at(
                computed, "fundsWithheldFromWithdrawal"
            ),
            profile_id=repository.profile_id,
            profile_label=repository.profile_label,
        )


def fetch_balance(repository: ETradeRepository, account_id_key: str) -> Balance:
    """Fetch one account's balance.

    E*TRADE's balance request needs the account's institution type, which only
    the account list has.

    Raises:
        ToolError: the profile has no open account with this key
    """
    logger.info("Fetching account balance")
    account = next(
        (
            account
            for account in fetch_accounts(repository)
            if account.account_id_key == account_id_key
        ),
        None,
    )
    if account is None:
        raise ToolError(
            f"Profile {repository.profile_id} has no open account with "
            f"account_id_key {account_id_key}. Use list_accounts to find the key."
        )

    data = repository.get(
        f"/v1/accounts/{account_id_key}/balance.json",
        params={"instType": account.institution_type, "realTimeNAV": "true"},
    )
    return Balance.from_etrade(data.get("BalanceResponse", {}), repository)


@tool(title="Get account balance", tags={"accounts", READ}, annotations=READS)
def get_account_balance(
    account_id_key: str,
    profile: str = "0",
    profiles: Profiles = Shared(configured_profiles),
) -> Balance:
    """Get one account's balances: cash, buying power, and total value.

    Includes the cash balance, the cash available to invest and to withdraw,
    cash and margin buying power, the money market sweep balance, the total
    account value in real time, and deposits or funds on hold.  Amounts are
    in USD.

    Args:
        account_id_key: The account's account_id_key from list_accounts (required)
        profile: Profile ID from list_profiles that owns the account
            (default: "0")

    Returns:
        Balance with the account's balances
    """
    return fetch_balance(profiles.repository(profile), account_id_key)


TOOLS: list[Callable[..., object]] = [list_accounts, get_account_balance]
