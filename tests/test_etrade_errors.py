"""
Test how E*TRADE API errors and unexpected errors reach the client.
"""

from typing import Any

import pytest
import requests
from conftest import FakeETrade, etrade_response
from fastmcp.client import Client, FastMCPTransport
from fastmcp.exceptions import ToolError

from etrade_errors import ETradeError

ACCOUNTS = "/v1/accounts/list.json"


@pytest.mark.parametrize(
    ("status", "body", "description"),
    [
        (
            401,
            {},
            "E*TRADE did not accept this profile's access token. The next call "
            "asks the user to authorize the profile again in a browser.",
        ),
        (
            429,
            {},
            "E*TRADE's rate limit is exhausted. Wait a minute and try again.",
        ),
        (
            400,
            {"Error": {"code": 100, "message": "Invalid account key"}},
            "E*TRADE returned 400: Invalid account key",
        ),
        (500, "<html>", "E*TRADE returned 500: Internal Server Error"),
    ],
)
def test_describe_a_failed_response(status: int, body: Any, description: str) -> None:
    error = ETradeError.from_response(etrade_response(body, status))

    assert str(error) == description


def test_describe_a_failed_response_with_no_reason() -> None:
    response = etrade_response({}, 503)
    response.reason = ""

    assert str(ETradeError.from_response(response)) == "E*TRADE returned 503: no detail"


async def test_etrade_errors_reach_the_client_with_etrade_detail(
    etrade: FakeETrade, mcp_client: Client[FastMCPTransport]
) -> None:
    etrade.answer(
        ACCOUNTS,
        {"Error": {"code": 100, "message": "Invalid account key"}},
        status=400,
    )

    with pytest.raises(ToolError, match="E\\*TRADE returned 400: Invalid account key"):
        await mcp_client.call_tool("list_accounts", {})


@pytest.mark.parametrize(
    ("error", "message"),
    [
        (requests.Timeout("secret detail"), "E\\*TRADE did not answer within 30"),
        (requests.ConnectionError("secret detail"), "Could not connect to E\\*TRADE"),
    ],
)
async def test_network_failures_reach_the_client(
    etrade: FakeETrade,
    mcp_client: Client[FastMCPTransport],
    error: requests.RequestException,
    message: str,
) -> None:
    etrade.answer(ACCOUNTS, error=error)

    with pytest.raises(ToolError, match=message) as raised:
        await mcp_client.call_tool("list_accounts", {})

    assert "secret detail" not in str(raised.value)


async def test_unexpected_errors_reach_the_client_without_detail(
    etrade: FakeETrade, mcp_client: Client[FastMCPTransport]
) -> None:
    etrade.answer(ACCOUNTS, error=requests.TooManyRedirects("internal secret"))

    with pytest.raises(ToolError) as raised:
        await mcp_client.call_tool("list_accounts", {})

    assert "internal secret" not in str(raised.value)
