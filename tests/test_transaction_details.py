"""
Test getting one transaction's details.
"""

from typing import Any

import pytest
from conftest import FakeETrade
from fastmcp.client import Client, FastMCPTransport
from fastmcp.exceptions import ToolError

DETAILS = "/v1/accounts/abc123xyz/transactions/18144100000861.json"


def details_json(**fields: Any) -> dict[str, Any]:
    """E*TRADE's transaction details, shaped like its example response: an ACH
    withdrawal with no category, memo, or order."""
    return {
        "TransactionDetailsResponse": {
            "transactionId": 18144100000861,
            "accountId": "835649790",
            "transactionDate": 1527134400000,
            "amount": -2.0,
            "description": "ACH WITHDRAWL REFID:77521276;",
            "Category": {
                "categoryId": "0",
                "parentId": "0",
                "categoryName": "",
                "parentName": "",
            },
            "Brokerage": {
                "transactionType": "Transfer",
                "Product": {},
                "quantity": 0.0,
                "price": 0.0,
                "settlementCurrency": "USD",
                "paymentCurrency": "USD",
                "fee": 0.0,
                "memo": "",
                "orderNo": "0",
            },
            **fields,
        }
    }


async def get_transaction(
    mcp_client: Client[FastMCPTransport], transaction_id: str = "18144100000861"
) -> dict[str, Any]:
    result = await mcp_client.call_tool(
        "get_transaction",
        {"account_id_key": "abc123xyz", "transaction_id": transaction_id},
    )
    assert result.structured_content is not None
    return result.structured_content


async def test_get_transaction(
    etrade: FakeETrade, mcp_client: Client[FastMCPTransport]
) -> None:
    etrade.answer(
        DETAILS,
        details_json(
            postDate=1527134400000,
            amount=-1751.99,
            description="Bought 10 AAPL @ 175.00",
            Category={
                "categoryId": "12",
                "parentId": "3",
                "categoryName": "Retirement",
                "parentName": "Investments",
            },
            Brokerage={
                "transactionType": "Bought",
                "Product": {"symbol": "AAPL", "securityType": "EQ"},
                "quantity": 10,
                "price": 175.0,
                "settlementCurrency": "USD",
                "paymentCurrency": "USD",
                "fee": 1.99,
                "memo": "Monthly buy",
                "checkNo": "",
                "orderNo": "482",
                "settlementDate": 1527307200000,
            },
        ),
    )

    transaction = await get_transaction(mcp_client)

    assert etrade.requests == [(DETAILS, {})]
    assert transaction == {
        "transaction_id": "18144100000861",
        "transaction_date": "2018-05-24",
        "post_date": "2018-05-24",
        "transaction_type": "Bought",
        "description": "Bought 10 AAPL @ 175.00",
        "amount": "-1751.99",
        "symbol": "AAPL",
        "security_type": "EQ",
        "quantity": "10",
        "price": "175.0",
        "fee": "1.99",
        "category": "Retirement",
        "parent_category": "Investments",
        "memo": "Monthly buy",
        "check_number": None,
        "order_number": "482",
        "settlement_date": "2018-05-26",
        "settlement_currency": "USD",
        "payment_currency": "USD",
        "account_id_key": "abc123xyz",
        "profile_id": "0",
        "profile_label": None,
    }


async def test_a_transfer_has_no_category_memo_or_order(
    etrade: FakeETrade, mcp_client: Client[FastMCPTransport]
) -> None:
    """E*TRADE's example sends empty names, an empty memo, and order number 0."""
    etrade.answer(DETAILS, details_json())

    transaction = await get_transaction(mcp_client)

    assert transaction["transaction_type"] == "Transfer"
    assert transaction["amount"] == "-2.0"
    assert transaction["symbol"] is None
    assert transaction["category"] is None
    assert transaction["parent_category"] is None
    assert transaction["memo"] is None
    assert transaction["order_number"] is None
    assert transaction["settlement_date"] is None


async def test_a_check_has_its_number(
    etrade: FakeETrade, mcp_client: Client[FastMCPTransport]
) -> None:
    etrade.answer(
        DETAILS,
        details_json(
            description="CHECK 1042",
            Brokerage={"transactionType": "Check", "checkNo": 1042, "orderNo": 0},
        ),
    )

    transaction = await get_transaction(mcp_client)

    assert transaction["check_number"] == "1042"
    assert transaction["order_number"] is None


@pytest.mark.parametrize(
    "details",
    [
        details_json(
            Category=None,
            Brokerage=None,
            category={"categoryName": "Income", "parentName": "Investments"},
            brokerage={
                "transactionType": "Dividend",
                "product": {"symbol": "SPY", "securityType": "EQ"},
                "memo": "Quarterly",
            },
        ),
        details_json(
            Brokerage={
                "transactionType": "Dividend",
                "Product": {"symbol": "SPY", "securityType": "EQ"},
            },
            Category={"categoryName": "Income", "parentName": "Investments"},
            memo="Quarterly",
        ),
    ],
)
async def test_either_documented_shape_of_the_details(
    etrade: FakeETrade, mcp_client: Client[FastMCPTransport], details: dict[str, Any]
) -> None:
    """E*TRADE's reference names category, brokerage, and product in lower case,
    and puts memo in brokerage.  Its details example capitalizes them, and its
    list example puts memo on the transaction."""
    etrade.answer(DETAILS, details)

    transaction = await get_transaction(mcp_client)

    assert transaction["transaction_type"] == "Dividend"
    assert transaction["symbol"] == "SPY"
    assert transaction["category"] == "Income"
    assert transaction["parent_category"] == "Investments"
    assert transaction["memo"] == "Quarterly"


async def test_a_transaction_e_trade_does_not_have(
    etrade: FakeETrade, mcp_client: Client[FastMCPTransport]
) -> None:
    etrade.answer(
        DETAILS,
        {
            "Error": {
                "code": 1001,
                "message": "Invalid Transaction Id. The Id passed does not exist "
                "for the specified account.",
            }
        },
        status=404,
    )

    with pytest.raises(ToolError, match="does not exist for the specified account"):
        await get_transaction(mcp_client)


async def test_a_transaction_with_no_details(
    etrade: FakeETrade, mcp_client: Client[FastMCPTransport]
) -> None:
    """E*TRADE answers 204 No Content, with an empty body."""
    etrade.answer(DETAILS, status=204)

    with pytest.raises(ToolError, match="no transaction 18144100000861 in the account"):
        await get_transaction(mcp_client)


@pytest.mark.parametrize(
    "transaction_id", ["../../orders", "18144100000861/Trades", ""]
)
async def test_a_transaction_id_is_only_digits(
    etrade: FakeETrade, mcp_client: Client[FastMCPTransport], transaction_id: str
) -> None:
    """The ID goes into the request's path, so it must not add a path segment."""
    with pytest.raises(ToolError, match="should match pattern"):
        await get_transaction(mcp_client, transaction_id)

    assert etrade.requests == []
