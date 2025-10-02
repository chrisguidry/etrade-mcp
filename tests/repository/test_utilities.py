"""Tests for E*TRADE repository utility functions."""

from decimal import Decimal

from repository import ETradeRepository


def test_extract_decimal(repository: ETradeRepository) -> None:
    """Test _extract_decimal utility method."""
    data = {"value": 123.45, "invalid": "not_a_number", "none": None}

    assert repository._extract_decimal(data, "value") == Decimal("123.45")
    assert repository._extract_decimal(data, "invalid") is None
    assert repository._extract_decimal(data, "none") is None
    assert repository._extract_decimal(data, "missing") is None
