"""
Test reading values out of E*TRADE's JSON responses.
"""

from datetime import date
from decimal import Decimal
from typing import Any

import pytest

from etrade_json import as_list, date_at, decimal_at


@pytest.mark.parametrize(
    ("value", "items"),
    [
        (None, []),
        ({"symbol": "AAPL"}, [{"symbol": "AAPL"}]),
        (
            [{"symbol": "AAPL"}, {"symbol": "SPY"}],
            [{"symbol": "AAPL"}, {"symbol": "SPY"}],
        ),
    ],
)
def test_as_list(value: Any, items: list[dict[str, Any]]) -> None:
    assert as_list(value) == items


@pytest.mark.parametrize(
    ("data", "value"),
    [
        ({"price": 123.45}, Decimal("123.45")),
        ({"price": 7}, Decimal("7")),
        ({"price": "not_a_number"}, None),
        ({"price": None}, None),
        ({}, None),
    ],
)
def test_decimal_at(data: dict[str, Any], value: Decimal | None) -> None:
    assert decimal_at(data, "price") == value


@pytest.mark.parametrize(
    ("data", "value"),
    [
        ({"transactionDate": 1528948800000}, date(2018, 6, 14)),
        ({"transactionDate": 1544418000000}, date(2018, 12, 10)),
        ({"transactionDate": "1528948800000"}, date(2018, 6, 14)),
        ({"transactionDate": "yesterday"}, None),
        ({"transactionDate": None}, None),
        ({}, None),
    ],
)
def test_date_at(data: dict[str, Any], value: date | None) -> None:
    """E*TRADE dates a transaction at midnight US Eastern time, in daylight
    time (04:00 UTC) and in standard time (05:00 UTC)."""
    assert date_at(data, "transactionDate") == value
