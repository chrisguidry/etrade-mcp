"""Tests for E*TRADE repository account operations."""

from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from repository import ETradeRepository


def test_get_accounts(
    repository: ETradeRepository, mock_oauth_session: MagicMock
) -> None:
    """Test getting list of accounts."""
    mock_response = {
        "AccountListResponse": {
            "Accounts": {
                "Account": [
                    {
                        "accountId": "12345678",
                        "accountIdKey": "abc123xyz",
                        "accountMode": "CASH",
                        "accountDesc": "My Account",
                        "accountType": "INDIVIDUAL",
                        "institutionType": "BROKERAGE",
                        "accountStatus": "ACTIVE",
                    }
                ]
            }
        }
    }
    mock_oauth_session.get.return_value.json.return_value = mock_response

    accounts = repository.get_accounts()

    assert len(accounts) == 1
    assert accounts[0].account_id == "12345678"
    assert accounts[0].account_id_key == "abc123xyz"
    assert accounts[0].account_desc == "My Account"


def test_get_accounts_single_dict(
    repository: ETradeRepository, mock_oauth_session: MagicMock
) -> None:
    """Test getting accounts when API returns a single dict instead of list."""
    mock_response = {
        "AccountListResponse": {
            "Accounts": {
                "Account": {
                    "accountId": "12345678",
                    "accountIdKey": "abc123xyz",
                    "accountMode": "CASH",
                    "accountDesc": "My Account",
                    "accountType": "INDIVIDUAL",
                    "institutionType": "BROKERAGE",
                    "accountStatus": "ACTIVE",
                }
            }
        }
    }
    mock_oauth_session.get.return_value.json.return_value = mock_response

    accounts = repository.get_accounts()

    assert len(accounts) == 1
    assert accounts[0].account_id == "12345678"


def test_get_accounts_filters_closed(
    repository: ETradeRepository, mock_oauth_session: MagicMock
) -> None:
    """Test that closed accounts are filtered out."""
    mock_response = {
        "AccountListResponse": {
            "Accounts": {
                "Account": [
                    {
                        "accountId": "12345678",
                        "accountIdKey": "abc123xyz",
                        "accountMode": "CASH",
                        "accountDesc": "Active Account",
                        "accountType": "INDIVIDUAL",
                        "institutionType": "BROKERAGE",
                        "accountStatus": "ACTIVE",
                    },
                    {
                        "accountId": "87654321",
                        "accountIdKey": "xyz321abc",
                        "accountMode": "CASH",
                        "accountDesc": "Closed Account",
                        "accountType": "INDIVIDUAL",
                        "institutionType": "BROKERAGE",
                        "accountStatus": "CLOSED",
                    },
                ]
            }
        }
    }
    mock_oauth_session.get.return_value.json.return_value = mock_response

    accounts = repository.get_accounts()

    assert len(accounts) == 1
    assert accounts[0].account_status == "ACTIVE"


def test_get_account_balance_account_not_found(
    repository: ETradeRepository, mock_oauth_session: MagicMock
) -> None:
    """Test get_account_balance raises ValueError when account not found."""
    accounts_response = {
        "AccountListResponse": {
            "Accounts": {
                "Account": {
                    "accountId": "12345678",
                    "accountIdKey": "abc123xyz",
                    "accountMode": "MARGIN",
                    "accountDesc": "My Account",
                    "accountType": "INDIVIDUAL",
                    "institutionType": "BROKERAGE",
                    "accountStatus": "ACTIVE",
                }
            }
        }
    }

    mock_oauth_session.get.return_value.json.return_value = accounts_response

    with pytest.raises(ValueError, match="Account not found: nonexistent"):
        repository.get_account_balance("nonexistent")


def test_get_account_balance(
    repository: ETradeRepository, mock_oauth_session: MagicMock
) -> None:
    """Test getting account balance."""
    accounts_response = {
        "AccountListResponse": {
            "Accounts": {
                "Account": {
                    "accountId": "12345678",
                    "accountIdKey": "abc123xyz",
                    "accountMode": "MARGIN",
                    "accountDesc": "My Account",
                    "accountType": "INDIVIDUAL",
                    "institutionType": "BROKERAGE",
                    "accountStatus": "ACTIVE",
                }
            }
        }
    }

    balance_response = {
        "BalanceResponse": {
            "accountId": "12345678",
            "accountType": "INDIVIDUAL",
            "accountDescription": "My Account",
            "accountMode": "MARGIN",
            "Computed": {
                "cashBalance": 5000.00,
                "cashBuyingPower": 5000.00,
                "marginBuyingPower": 10000.00,
                "RealTimeValues": {
                    "totalAccountValue": 25000.00,
                    "netAccountValue": 25000.00,
                },
            },
        }
    }

    def mock_get(url: str, params: dict[str, str] | None = None) -> MagicMock:
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        if "balance" in url:
            mock_resp.json.return_value = balance_response
        else:
            mock_resp.json.return_value = accounts_response
        return mock_resp

    mock_oauth_session.get.side_effect = mock_get

    balance = repository.get_account_balance("abc123xyz")

    assert balance.account_id == "12345678"
    assert balance.cash_balance == Decimal("5000.00")
    assert balance.total_account_value == Decimal("25000.00")
