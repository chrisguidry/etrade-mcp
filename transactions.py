"""
Transactions: the activity in a brokerage account, such as trades, dividends,
deposits, and withdrawals.

E*TRADE's List Transactions API answers with at most 50 transactions a request.
Each response has a marker, and the next request passes it to continue from the
last transaction.  E*TRADE documents that the series ends with a page shorter
than the count requested.  Its example responses set moreTransactions to false
even when more transactions follow, so this does not read that field.

E*TRADE's List Transaction Details API answers for one transaction, with the
fields the list has and a few more: the category, memo, check number, order
number, and settlement details.

https://apisb.etrade.com/docs/api/account/api-transaction-v1.html
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Annotated, Any

from fastmcp.dependencies import Shared
from fastmcp.exceptions import ToolError
from fastmcp.tools import tool
from pydantic import BaseModel, Field

from effects import READ, READS
from etrade_json import EASTERN, as_list, date_at, decimal_at, text_at
from pagination import PaginationInfo, paginate
from profiles import Profiles, configured_profiles
from repository import ETradeRepository

logger = logging.getLogger(__name__)

# The most transactions E*TRADE returns in one response.
PAGE_SIZE = 50

# A limit on the pages read, so that one call sends a bounded number of
# requests.  At 50 transactions a page, this is 1,000 transactions.
MAXIMUM_PAGES = 20

# The date range a call covers when it gives no start date.
DEFAULT_DAYS = 30

# E*TRADE's transaction IDs are integers.  The ID is part of the request's path,
# so any other character could name a different endpoint.
TRANSACTION_ID_PATTERN = r"^\d+$"


def brokerage_of(transaction: dict[str, Any]) -> dict[str, Any]:
    """The transaction's brokerage object, which holds its type, security, and
    trade details.

    E*TRADE's transaction list example names it brokerage, and its transaction
    details example names it Brokerage.  This reads either.
    """
    return transaction.get("brokerage") or transaction.get("Brokerage") or {}


class Transaction(BaseModel):
    """One transaction in a brokerage account."""

    transaction_id: str = Field(
        ...,
        description="E*TRADE's ID for the transaction.  Pass it to get_transaction "
        "for the transaction's details",
    )
    transaction_date: date | None = Field(
        None, description="The date of the transaction"
    )
    post_date: date | None = Field(
        None, description="The date E*TRADE posted the transaction to the account"
    )
    transaction_type: str | None = Field(
        None,
        description="E*TRADE's type for the transaction, such as 'Bought', "
        "'Sold', 'Dividend', or 'Transfer'",
    )
    description: str = Field(..., description="E*TRADE's description")
    amount: Decimal | None = Field(
        None,
        description="The total amount in USD, including any commission.  "
        "Negative when money leaves the account",
    )

    # The security, for a transaction that has one
    symbol: str | None = Field(
        None, description="The security's symbol.  Null when there is no security"
    )
    security_type: str | None = Field(
        None,
        description="The security's type code, such as 'EQ' (equity), 'MF' "
        "(mutual fund), or 'OPTN' (option).  Null when there is no security",
    )
    quantity: Decimal | None = Field(
        None, description="The number of shares or units.  0 when there are none"
    )
    price: Decimal | None = Field(
        None, description="The price per share or unit.  0 when there is none"
    )
    fee: Decimal | None = Field(None, description="The brokerage fee")

    @classmethod
    def from_etrade(cls, transaction: dict[str, Any]) -> Transaction:
        """Convert one transaction from E*TRADE's transaction list or details.

        E*TRADE's reference puts transactionType inside the brokerage object,
        and so does its details example.  Its list example puts transactionType
        on the transaction, and names the product object product where the
        details example names it Product.  This reads either.
        """
        brokerage = brokerage_of(transaction)
        product = brokerage.get("product") or brokerage.get("Product") or {}
        return cls(
            transaction_id=str(transaction.get("transactionId", "")),
            transaction_date=date_at(transaction, "transactionDate"),
            post_date=date_at(transaction, "postDate"),
            transaction_type=(
                transaction.get("transactionType") or brokerage.get("transactionType")
            ),
            description=transaction.get("description", ""),
            amount=decimal_at(transaction, "amount"),
            symbol=product.get("symbol"),
            security_type=product.get("securityType"),
            quantity=decimal_at(brokerage, "quantity"),
            price=decimal_at(brokerage, "price"),
            fee=decimal_at(brokerage, "fee"),
        )


class TransactionDetails(Transaction):
    """One transaction in a brokerage account, with the details that E*TRADE
    gives only for one transaction at a time."""

    category: str | None = Field(
        None,
        description="The category the user gave the transaction in E*TRADE.  "
        "Null when it has none",
    )
    parent_category: str | None = Field(
        None, description="The category that holds category.  Null when there is none"
    )
    memo: str | None = Field(
        None, description="The transaction's memo.  Null when it has none"
    )
    check_number: str | None = Field(
        None, description="The check number, for a check.  Null for anything else"
    )
    order_number: str | None = Field(
        None,
        description="The number of the order that made the trade.  Null when no "
        "order made the transaction",
    )
    settlement_date: date | None = Field(
        None,
        description="The date the transaction settles.  Null when E*TRADE does not "
        "send one",
    )
    settlement_currency: str | None = Field(
        None, description="The currency the transaction settles in, such as 'USD'"
    )
    payment_currency: str | None = Field(
        None, description="The currency the transaction is paid in, such as 'USD'"
    )

    account_id_key: str = Field(..., description="The account's account_id_key")
    profile_id: str = Field(..., description="Profile identifier for this account")
    profile_label: str | None = Field(
        None, description="Human-readable label for this profile"
    )

    @classmethod
    def from_etrade_details(
        cls,
        details: dict[str, Any],
        account_id_key: str,
        repository: ETradeRepository,
    ) -> TransactionDetails:
        """Convert E*TRADE's details for one transaction.

        E*TRADE's reference names the category object category and puts memo
        inside the brokerage object.  Its details example names it Category,
        and its list example puts memo on the transaction.  This reads either.
        """
        brokerage = brokerage_of(details)
        category = details.get("category") or details.get("Category") or {}
        return cls(
            **Transaction.from_etrade(details).model_dump(),
            category=text_at(category, "categoryName"),
            parent_category=text_at(category, "parentName"),
            memo=text_at(brokerage, "memo") or text_at(details, "memo"),
            check_number=reference_number_at(brokerage, "checkNo"),
            order_number=reference_number_at(brokerage, "orderNo"),
            settlement_date=date_at(brokerage, "settlementDate"),
            settlement_currency=text_at(brokerage, "settlementCurrency"),
            payment_currency=text_at(brokerage, "paymentCurrency"),
            account_id_key=account_id_key,
            profile_id=repository.profile_id,
            profile_label=repository.profile_label,
        )


def reference_number_at(data: dict[str, Any], key: str) -> str | None:
    """Read an order or check number, or None when there is none.

    E*TRADE's details example sends order number 0 for a transfer, which no
    order made.
    """
    number = text_at(data, key)
    return None if number == "0" else number


def fetch_transactions(
    repository: ETradeRepository, account_id_key: str, start: date, end: date
) -> tuple[list[Transaction], bool]:
    """Fetch an account's transactions in a date range, newest first.

    Returns:
        The transactions, and whether the range has more than the page limit
        allowed this to read
    """
    logger.info("Fetching account transactions")
    params = {
        "startDate": start.strftime("%m%d%Y"),
        "endDate": end.strftime("%m%d%Y"),
        "sortOrder": "DESC",
        "count": str(PAGE_SIZE),
    }
    transactions: list[Transaction] = []
    for _ in range(MAXIMUM_PAGES):
        data = repository.get(
            f"/v1/accounts/{account_id_key}/transactions.json", params=params
        )
        response = data.get("TransactionListResponse", {})
        page = as_list(response.get("Transaction"))
        transactions.extend(Transaction.from_etrade(t) for t in page)

        marker = response.get("marker")
        if len(page) < PAGE_SIZE or not marker:
            return transactions, False
        params = {**params, "marker": str(marker)}
    return transactions, True


class TransactionsResponse(BaseModel):
    """One page of an account's transactions in a date range."""

    account_id_key: str = Field(..., description="The account's account_id_key")
    start_date: date = Field(..., description="The first date in the range")
    end_date: date = Field(..., description="The last date in the range")
    transactions: list[Transaction] = Field(
        default_factory=list,
        description="One page of the transactions in the range, newest first",
    )
    truncated: bool = Field(
        ...,
        description="True when the server stopped at its limit of 1,000 "
        "transactions, so the range may hold older ones it did not read.  "
        "Narrow the date range to read them",
    )
    profile_id: str = Field(..., description="Profile identifier for this account")
    profile_label: str | None = Field(
        None, description="Human-readable label for this profile"
    )
    pagination: PaginationInfo = Field(..., description="Pagination information")


@tool(title="Get transactions", tags={"transactions", READ}, annotations=READS)
def get_transactions(
    account_id_key: str,
    start_date: date | None = None,
    end_date: date | None = None,
    profile: str = "0",
    limit: int = 100,
    offset: int = 0,
    profiles: Profiles = Shared(configured_profiles),
) -> TransactionsResponse:
    """List the transactions in one brokerage account over a date range.

    Use it to see trades, dividends, interest, fees, deposits, and withdrawals,
    and to reconcile the account with a budget.  Each transaction has its
    date, type, description, and amount, and, for a trade or a dividend, the
    security, quantity, price, and fee.  Amounts are in USD.  Transactions
    come newest first.  For one transaction's category, memo, check number,
    order number, and settlement date, pass its transaction_id to
    get_transaction.

    E*TRADE lists transactions only for brokerage accounts, and keeps about two
    years of history.  The server reads at most 1,000 transactions in the
    range; truncated says when it stopped there.

    Args:
        account_id_key: The account's account_id_key from list_accounts (required)
        start_date: The first date to include, as YYYY-MM-DD (default: 30 days
            before end_date)
        end_date: The last date to include, as YYYY-MM-DD (default: today in US
            Eastern time)
        profile: Profile ID from list_profiles that owns the account
            (default: "0")
        limit: Maximum number of transactions to return (default: 100)
        offset: Number of transactions to skip, for the next page (default: 0)

    Returns:
        TransactionsResponse with one page of transactions, the date range, and
        pagination information
    """
    end = end_date or datetime.now(EASTERN).date()
    start = start_date or end - timedelta(days=DEFAULT_DAYS)
    if start > end:
        raise ToolError(
            f"start_date {start} is after end_date {end}. "
            "Pass a start_date on or before the end_date."
        )

    repository = profiles.repository(profile)
    transactions, truncated = fetch_transactions(repository, account_id_key, start, end)
    page, pagination = paginate(transactions, limit, offset)
    return TransactionsResponse(
        account_id_key=account_id_key,
        start_date=start,
        end_date=end,
        transactions=page,
        truncated=truncated,
        profile_id=repository.profile_id,
        profile_label=repository.profile_label,
        pagination=pagination,
    )


def fetch_transaction_details(
    repository: ETradeRepository, account_id_key: str, transaction_id: str
) -> TransactionDetails:
    """Fetch one transaction's details.

    Raises:
        ToolError: E*TRADE answered with no transaction
    """
    logger.info("Fetching transaction details")
    data = repository.get(
        f"/v1/accounts/{account_id_key}/transactions/{transaction_id}.json"
    )
    details = data.get("TransactionDetailsResponse")
    if not details:
        raise ToolError(
            f"E*TRADE has no transaction {transaction_id} in the account with "
            f"account_id_key {account_id_key}. Use get_transactions to find the "
            "transaction_id."
        )
    return TransactionDetails.from_etrade_details(details, account_id_key, repository)


@tool(title="Get transaction", tags={"transactions", READ}, annotations=READS)
def get_transaction(
    account_id_key: str,
    transaction_id: Annotated[str, Field(pattern=TRANSACTION_ID_PATTERN)],
    profile: str = "0",
    profiles: Profiles = Shared(configured_profiles),
) -> TransactionDetails:
    """Get one transaction in a brokerage account, with its details.

    Returns everything get_transactions returns for the transaction, plus its
    category, memo, check number, order number, settlement date, and
    settlement and payment currencies.  Use it to match a transaction to an
    entry in a budget when the date, type, description, and amount are not
    enough.  Amounts are in USD.

    Args:
        account_id_key: The account's account_id_key from list_accounts (required)
        transaction_id: The transaction's transaction_id from get_transactions,
            which is only digits (required)
        profile: Profile ID from list_profiles that owns the account
            (default: "0")

    Returns:
        TransactionDetails with the transaction and its details
    """
    repository = profiles.repository(profile)
    return fetch_transaction_details(repository, account_id_key, transaction_id)


TOOLS: list[Callable[..., object]] = [get_transactions, get_transaction]
