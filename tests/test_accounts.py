"""
Test listing accounts and reading their balances.
"""

import pytest
from conftest import FakeETrade, account_json, account_list
from fastmcp.client import Client, FastMCPTransport
from fastmcp.exceptions import ToolError

ACCOUNTS = "/v1/accounts/list.json"
BALANCE = "/v1/accounts/abc123xyz/balance.json"


async def test_list_accounts(
    etrade: FakeETrade, mcp_client: Client[FastMCPTransport]
) -> None:
    etrade.answer(ACCOUNTS, account_list(account_json()))

    result = await mcp_client.call_tool("list_accounts", {})

    assert result.structured_content == {
        "accounts": [
            {
                "account_id": "12345678",
                "account_id_key": "abc123xyz",
                "account_mode": "MARGIN",
                "account_desc": "Brokerage",
                "account_name": "Long-term",
                "account_type": "INDIVIDUAL",
                "institution_type": "BROKERAGE",
                "account_status": "ACTIVE",
                "closed_date": None,
                "profile_id": "0",
                "profile_label": None,
            }
        ],
        "pagination": {"total_count": 1, "limit": 100, "offset": 0, "has_more": False},
    }


async def test_list_accounts_leaves_out_closed_accounts(
    etrade: FakeETrade, mcp_client: Client[FastMCPTransport]
) -> None:
    etrade.answer(
        ACCOUNTS,
        account_list(
            account_json("open"),
            account_json("closed", status="CLOSED"),
        ),
    )

    result = await mcp_client.call_tool("list_accounts", {})

    assert result.structured_content is not None
    accounts = result.structured_content["accounts"]
    assert [account["account_id_key"] for account in accounts] == ["open"]


async def test_list_accounts_pages(
    etrade: FakeETrade, mcp_client: Client[FastMCPTransport]
) -> None:
    etrade.answer(
        ACCOUNTS, account_list(account_json("a"), account_json("b"), account_json("c"))
    )

    result = await mcp_client.call_tool("list_accounts", {"limit": 1, "offset": 1})

    assert result.structured_content is not None
    accounts = result.structured_content["accounts"]
    assert [account["account_id_key"] for account in accounts] == ["b"]
    assert result.structured_content["pagination"] == {
        "total_count": 3,
        "limit": 1,
        "offset": 1,
        "has_more": True,
    }


async def test_list_accounts_rejects_an_unknown_profile(
    etrade: FakeETrade, mcp_client: Client[FastMCPTransport]
) -> None:
    with pytest.raises(ToolError, match=r"Profile 9 not found\. Available profiles: 0"):
        await mcp_client.call_tool("list_accounts", {"profile": "9"})


async def test_get_account_balance(
    etrade: FakeETrade, mcp_client: Client[FastMCPTransport]
) -> None:
    etrade.answer(ACCOUNTS, account_list(account_json()))
    etrade.answer(
        BALANCE,
        {
            "BalanceResponse": {
                "accountId": "12345678",
                "accountType": "INDIVIDUAL",
                "accountDescription": "Brokerage",
                "accountMode": "MARGIN",
                "Cash": {"moneyMktBalance": 1200.5},
                "Computed": {
                    "cashBalance": 5000.00,
                    "cashBuyingPower": 5000.00,
                    "marginBuyingPower": 10000.00,
                    "cashAvailableForInvestment": 4800.25,
                    "cashAvailableForWithdrawal": 4700.75,
                    "settledCashForInvestment": 4000,
                    "unSettledCashForInvestment": 800.25,
                    "netCash": 4900,
                    "unclearedDeposits": 100,
                    "fundsWithheldFromPurchasePower": 0,
                    "fundsWithheldFromWithdrawal": 0,
                    "RealTimeValues": {
                        "totalAccountValue": 25000.00,
                        "netAccountValue": 24000.00,
                    },
                },
            }
        },
    )

    result = await mcp_client.call_tool(
        "get_account_balance", {"account_id_key": "abc123xyz"}
    )

    assert result.structured_content == {
        "account_id": "12345678",
        "account_type": "INDIVIDUAL",
        "account_description": "Brokerage",
        "account_mode": "MARGIN",
        "cash_balance": "5000.0",
        "cash_buying_power": "5000.0",
        "margin_buying_power": "10000.0",
        "cash_available_for_investment": "4800.25",
        "cash_available_for_withdrawal": "4700.75",
        "settled_cash_for_investment": "4000",
        "unsettled_cash_for_investment": "800.25",
        "net_cash": "4900",
        "money_market_balance": "1200.5",
        "total_account_value": "25000.0",
        "net_account_value": "24000.0",
        "uncleared_deposits": "100",
        "funds_withheld_from_purchase_power": "0",
        "funds_withheld_from_withdrawal": "0",
        "profile_id": "0",
        "profile_label": None,
    }
    assert (BALANCE, {"instType": "BROKERAGE", "realTimeNAV": "true"}) in (
        etrade.requests
    )


async def test_get_account_balance_of_an_unknown_account(
    etrade: FakeETrade, mcp_client: Client[FastMCPTransport]
) -> None:
    etrade.answer(ACCOUNTS, account_list(account_json()))

    with pytest.raises(
        ToolError,
        match="Profile 0 has no open account with account_id_key nonexistent",
    ):
        await mcp_client.call_tool(
            "get_account_balance", {"account_id_key": "nonexistent"}
        )
