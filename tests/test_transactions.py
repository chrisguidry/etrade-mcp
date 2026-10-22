"""
Test listing an account's transactions.
"""

from datetime import UTC, date, datetime, timedelta
from typing import Any

import pytest
from conftest import FakeETrade
from fastmcp.client import Client, FastMCPTransport
from fastmcp.exceptions import ToolError

from transactions import MAXIMUM_PAGES, PAGE_SIZE

TRANSACTIONS = "/v1/accounts/abc123xyz/transactions.json"

OCTOBER = {"start_date": "2026-10-01", "end_date": "2026-10-21"}


def october_request(**params: str) -> dict[str, str]:
    """The query E*TRADE receives for the October date range."""
    return {
        "startDate": "10012026",
        "endDate": "10212026",
        "sortOrder": "DESC",
        "count": str(PAGE_SIZE),
        **params,
    }


def transaction_json(transaction_id: int = 1, **fields: Any) -> dict[str, Any]:
    """One transaction from E*TRADE's transaction list: an ACH withdrawal."""
    return {
        "transactionId": transaction_id,
        "accountId": "835649790",
        "transactionDate": 1791777600000,
        "postDate": 1791777600000,
        "amount": -2,
        "description": "ACH WITHDRAWL REFID:109187276;",
        "transactionType": "Transfer",
        "instType": "BROKERAGE",
        "brokerage": {
            "product": {},
            "quantity": 0,
            "price": 0,
            "settlementCurrency": "USD",
            "paymentCurrency": "USD",
            "fee": 0,
        },
        **fields,
    }


def transaction_list(
    *transactions: dict[str, Any], marker: str | None = None
) -> dict[str, Any]:
    """E*TRADE's transaction list.  One transaction arrives as a bare object."""
    listed: Any = transactions[0] if len(transactions) == 1 else list(transactions)
    response: dict[str, Any] = {
        "Transaction": listed,
        "transactionCount": len(transactions),
    }
    if marker is not None:
        response["marker"] = marker
    return {"TransactionListResponse": response}


def full_page(first_id: int, marker: str) -> dict[str, Any]:
    """A page with as many transactions as the server asks for."""
    return transaction_list(
        *(transaction_json(first_id + n) for n in range(PAGE_SIZE)), marker=marker
    )


async def get_transactions(
    mcp_client: Client[FastMCPTransport], **arguments: Any
) -> dict[str, Any]:
    result = await mcp_client.call_tool(
        "get_transactions", {"account_id_key": "abc123xyz", **arguments}
    )
    assert result.structured_content is not None
    return result.structured_content


async def test_get_transactions(
    etrade: FakeETrade, mcp_client: Client[FastMCPTransport]
) -> None:
    purchase = transaction_json(
        18165100001766,
        amount=-1751.99,
        description="Bought 10 AAPL @ 175.00",
        transactionType="Bought",
        brokerage={
            "product": {"symbol": "AAPL", "securityType": "EQ"},
            "quantity": 10,
            "price": 175.0,
            "fee": 1.99,
        },
    )
    etrade.answer(TRANSACTIONS, transaction_list(purchase))

    transactions = await get_transactions(mcp_client, **OCTOBER)

    assert etrade.requests == [(TRANSACTIONS, october_request())]
    assert transactions == {
        "account_id_key": "abc123xyz",
        "start_date": "2026-10-01",
        "end_date": "2026-10-21",
        "transactions": [
            {
                "transaction_id": "18165100001766",
                "transaction_date": "2026-10-12",
                "post_date": "2026-10-12",
                "transaction_type": "Bought",
                "description": "Bought 10 AAPL @ 175.00",
                "amount": "-1751.99",
                "symbol": "AAPL",
                "security_type": "EQ",
                "quantity": "10",
                "price": "175.0",
                "fee": "1.99",
            }
        ],
        "truncated": False,
        "profile_id": "0",
        "profile_label": None,
        "pagination": {"total_count": 1, "limit": 100, "offset": 0, "has_more": False},
    }


async def test_a_transfer_has_no_security(
    etrade: FakeETrade, mcp_client: Client[FastMCPTransport]
) -> None:
    etrade.answer(TRANSACTIONS, transaction_list(transaction_json()))

    transactions = await get_transactions(mcp_client, **OCTOBER)

    [transfer] = transactions["transactions"]
    assert transfer["transaction_type"] == "Transfer"
    assert transfer["amount"] == "-2"
    assert transfer["symbol"] is None
    assert transfer["security_type"] is None


@pytest.mark.parametrize(
    "transaction",
    [
        transaction_json(
            transactionType=None,
            brokerage=None,
            Brokerage={
                "transactionType": "Dividend",
                "Product": {"symbol": "SPY", "securityType": "EQ"},
            },
        ),
        transaction_json(
            brokerage={
                "transactionType": "Dividend",
                "product": {"symbol": "SPY", "securityType": "EQ"},
            },
            transactionType="Dividend",
        ),
    ],
)
async def test_either_documented_shape_of_a_transaction(
    etrade: FakeETrade,
    mcp_client: Client[FastMCPTransport],
    transaction: dict[str, Any],
) -> None:
    """E*TRADE's reference puts transactionType inside the brokerage object,
    and its details example capitalizes Brokerage and Product.  Its list
    example uses lower case and puts transactionType on the transaction."""
    etrade.answer(TRANSACTIONS, transaction_list(transaction))

    transactions = await get_transactions(mcp_client, **OCTOBER)

    [dividend] = transactions["transactions"]
    assert dividend["transaction_type"] == "Dividend"
    assert dividend["symbol"] == "SPY"


async def test_get_transactions_follows_the_marker_to_the_next_page(
    etrade: FakeETrade, mcp_client: Client[FastMCPTransport]
) -> None:
    etrade.answer(
        TRANSACTIONS, full_page(1000, marker="page-2"), params=october_request()
    )
    etrade.answer(
        TRANSACTIONS,
        transaction_list(transaction_json(2000), marker="page-3"),
        params=october_request(marker="page-2"),
    )

    transactions = await get_transactions(mcp_client, **OCTOBER, limit=1000)

    assert len(etrade.requests) == 2
    assert len(transactions["transactions"]) == PAGE_SIZE + 1
    assert transactions["transactions"][-1]["transaction_id"] == "2000"
    assert transactions["truncated"] is False


async def test_a_full_page_with_no_marker_is_the_last(
    etrade: FakeETrade, mcp_client: Client[FastMCPTransport]
) -> None:
    page = full_page(1000, marker="unused")
    del page["TransactionListResponse"]["marker"]
    etrade.answer(TRANSACTIONS, page)

    transactions = await get_transactions(mcp_client, **OCTOBER)

    assert len(etrade.requests) == 1
    assert transactions["truncated"] is False


async def test_get_transactions_reads_at_most_the_page_limit(
    etrade: FakeETrade, mcp_client: Client[FastMCPTransport]
) -> None:
    etrade.answer(TRANSACTIONS, full_page(1000, marker="again"))

    transactions = await get_transactions(mcp_client, **OCTOBER)

    assert len(etrade.requests) == MAXIMUM_PAGES
    assert transactions["pagination"]["total_count"] == PAGE_SIZE * MAXIMUM_PAGES
    assert transactions["truncated"] is True


async def test_get_transactions_pages_transactions(
    etrade: FakeETrade, mcp_client: Client[FastMCPTransport]
) -> None:
    etrade.answer(
        TRANSACTIONS,
        transaction_list(transaction_json(3), transaction_json(2), transaction_json(1)),
    )

    transactions = await get_transactions(mcp_client, **OCTOBER, limit=1, offset=1)

    ids = [listed["transaction_id"] for listed in transactions["transactions"]]
    assert ids == ["2"]
    assert transactions["pagination"] == {
        "total_count": 3,
        "limit": 1,
        "offset": 1,
        "has_more": True,
    }


async def test_a_date_range_with_no_transactions(
    etrade: FakeETrade, mcp_client: Client[FastMCPTransport]
) -> None:
    """E*TRADE answers 204 No Content, with an empty body."""
    etrade.answer(TRANSACTIONS, status=204)

    transactions = await get_transactions(mcp_client, **OCTOBER)

    assert transactions["transactions"] == []
    assert transactions["truncated"] is False


def eastern_today() -> date:
    return (datetime.now(UTC) - timedelta(hours=4)).date()


@pytest.mark.parametrize(
    ("arguments", "start_date", "end_date"),
    [
        ({}, lambda: eastern_today() - timedelta(days=30), eastern_today),
        ({"start_date": "2026-10-01"}, lambda: date(2026, 10, 1), eastern_today),
        (
            {"end_date": "2026-10-21"},
            lambda: date(2026, 9, 21),
            lambda: date(2026, 10, 21),
        ),
    ],
)
async def test_the_default_date_range(
    etrade: FakeETrade,
    mcp_client: Client[FastMCPTransport],
    arguments: dict[str, str],
    start_date: Any,
    end_date: Any,
) -> None:
    etrade.answer(TRANSACTIONS, transaction_list(transaction_json()))

    transactions = await get_transactions(mcp_client, **arguments)

    assert transactions["start_date"] == start_date().isoformat()
    assert transactions["end_date"] == end_date().isoformat()
    [(_, params)] = etrade.requests
    assert params["startDate"] == start_date().strftime("%m%d%Y")
    assert params["endDate"] == end_date().strftime("%m%d%Y")


async def test_a_start_date_after_the_end_date_is_refused(
    etrade: FakeETrade, mcp_client: Client[FastMCPTransport]
) -> None:
    with pytest.raises(ToolError, match="start_date 2026-10-21 is after end_date"):
        await mcp_client.call_tool(
            "get_transactions",
            {
                "account_id_key": "abc123xyz",
                "start_date": "2026-10-21",
                "end_date": "2026-10-01",
            },
        )

    assert etrade.requests == []


async def test_a_bank_account_has_no_transactions_to_list(
    etrade: FakeETrade, mcp_client: Client[FastMCPTransport]
) -> None:
    etrade.answer(
        TRANSACTIONS,
        {
            "Error": {
                "code": 2001,
                "message": "Invalid account type. Only brokerage accounts are "
                "available.",
            }
        },
        status=400,
    )

    with pytest.raises(ToolError, match="Only brokerage accounts are available"):
        await get_transactions(mcp_client, **OCTOBER)
