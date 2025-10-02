"""Tests for E*TRADE repository portfolio operations."""

from decimal import Decimal
from unittest.mock import MagicMock

from repository import ETradeRepository


def test_get_account_portfolio_dict_account_portfolios(
    repository: ETradeRepository, mock_oauth_session: MagicMock
) -> None:
    """Test get_account_portfolio when API returns dict for AccountPortfolio."""
    mock_response = {
        "PortfolioResponse": {
            "AccountPortfolio": {  # Single dict instead of list
                "Position": {  # Single dict instead of list
                    "symbolDescription": "APPLE INC COM",
                    "quantity": 10,
                    "marketValue": 1750.00,
                    "Product": {"securityType": "EQ"},
                    "Quick": {"lastTrade": 175.00},
                }
            }
        }
    }
    mock_oauth_session.get.return_value.json.return_value = mock_response

    portfolio = repository.get_account_portfolio("abc123xyz")

    assert portfolio.account_id == "abc123xyz"
    assert len(portfolio.positions) == 1


def test_get_account_portfolio_list_with_dict_position(
    repository: ETradeRepository, mock_oauth_session: MagicMock
) -> None:
    """Test get_account_portfolio when AccountPortfolio is list but Position is dict."""
    mock_response = {
        "PortfolioResponse": {
            "AccountPortfolio": [  # List of portfolios
                {
                    "Position": {  # Single dict instead of list
                        "symbolDescription": "MSFT",
                        "quantity": 5,
                        "marketValue": 1900.00,
                        "Product": {"securityType": "EQ"},
                        "Quick": {"lastTrade": 380.00},
                    }
                }
            ]
        }
    }
    mock_oauth_session.get.return_value.json.return_value = mock_response

    portfolio = repository.get_account_portfolio("abc123xyz")

    assert portfolio.account_id == "abc123xyz"
    assert len(portfolio.positions) == 1


def test_get_account_portfolio_with_list_positions(
    repository: ETradeRepository, mock_oauth_session: MagicMock
) -> None:
    """Test get_account_portfolio when Position is a list (not dict)."""
    mock_response = {
        "PortfolioResponse": {
            "AccountPortfolio": {
                "Position": [  # Already a list
                    {
                        "symbolDescription": "AAPL",
                        "quantity": 10,
                        "marketValue": 1750.00,
                        "Product": {"securityType": "EQ"},
                        "Quick": {"lastTrade": 175.00},
                    },
                    {
                        "symbolDescription": "MSFT",
                        "quantity": 5,
                        "Product": {"securityType": "EQ"},
                        "Quick": {},
                        # No marketValue - test branch where market_value is None
                    },
                ]
            }
        }
    }
    mock_oauth_session.get.return_value.json.return_value = mock_response

    portfolio = repository.get_account_portfolio("abc123xyz")

    assert portfolio.account_id == "abc123xyz"
    assert len(portfolio.positions) == 2
    assert portfolio.total_market_value == Decimal(
        "1750.00"
    )  # Only AAPL has market value


def test_get_account_portfolio(
    repository: ETradeRepository, mock_oauth_session: MagicMock
) -> None:
    """Test getting account portfolio."""
    mock_response = {
        "PortfolioResponse": {
            "AccountPortfolio": {
                "Position": {
                    "symbolDescription": "APPLE INC COM",
                    "quantity": 10,
                    "pricePaid": 150.00,
                    "totalCost": 1500.00,
                    "marketValue": 1750.00,
                    "totalGain": 250.00,
                    "Product": {
                        "securityType": "EQ",
                    },
                    "Quick": {
                        "lastTrade": 175.00,
                    },
                }
            }
        }
    }
    mock_oauth_session.get.return_value.json.return_value = mock_response

    portfolio = repository.get_account_portfolio("abc123xyz")

    assert portfolio.account_id == "abc123xyz"
    assert len(portfolio.positions) == 1
    assert portfolio.positions[0].symbol == "APPLE INC COM"
    assert portfolio.positions[0].quantity == Decimal("10")
    assert portfolio.total_market_value == Decimal("1750.00")
