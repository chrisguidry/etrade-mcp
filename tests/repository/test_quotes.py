"""Tests for E*TRADE repository quote operations."""

from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from repository import ETradeRepository


def test_get_quotes(
    repository: ETradeRepository, mock_oauth_session: MagicMock
) -> None:
    """Test getting quotes for a single symbol."""
    mock_response = {
        "QuoteResponse": {
            "QuoteData": {
                "Product": {
                    "symbol": "AAPL",
                    "companyName": "Apple Inc.",
                    "securityType": "EQ",
                },
                "All": {
                    "lastTrade": 175.00,
                    "bid": 174.95,
                    "ask": 175.05,
                    "change": 1.50,
                    "totalVolume": 50_000_000,
                },
            }
        }
    }
    mock_oauth_session.get.return_value.json.return_value = mock_response

    quotes = repository.get_quotes(["AAPL"])

    assert len(quotes) == 1
    assert quotes[0].symbol == "AAPL"
    assert quotes[0].last_trade == Decimal("175.00")


def test_get_quotes_multiple_symbols(
    repository: ETradeRepository, mock_oauth_session: MagicMock
) -> None:
    """Test getting quotes for multiple symbols."""
    mock_response = {
        "QuoteResponse": {
            "QuoteData": [
                {
                    "Product": {"symbol": "AAPL", "securityType": "EQ"},
                    "All": {"lastTrade": 175.00},
                },
                {
                    "Product": {"symbol": "MSFT", "securityType": "EQ"},
                    "All": {"lastTrade": 380.00},
                },
            ]
        }
    }
    mock_oauth_session.get.return_value.json.return_value = mock_response

    quotes = repository.get_quotes(["AAPL", "MSFT"])

    assert len(quotes) == 2
    assert quotes[0].symbol == "AAPL"
    assert quotes[1].symbol == "MSFT"


def test_get_quotes_too_many_symbols(repository: ETradeRepository) -> None:
    """Test that getting quotes fails when too many symbols requested."""
    symbols = [f"SYM{i}" for i in range(26)]

    with pytest.raises(ValueError, match="Maximum 25 symbols"):
        repository.get_quotes(symbols)


def test_get_quotes_empty_list(repository: ETradeRepository) -> None:
    """Test getting quotes with empty symbol list."""
    quotes = repository.get_quotes([])
    assert quotes == []
