"""
Reading values out of E*TRADE's JSON responses.

E*TRADE converts its XML responses to JSON, so an element that repeats becomes a
list only when it repeats: one account, position, or quote arrives as a bare
object.  Its numbers are JSON floats, which this server reads as Decimals.
"""

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from typing import Any

# E*TRADE dates a transaction at midnight US Eastern time.  At UTC-4, midnight
# EDT is 00:00 and midnight EST is 01:00, so both fall on the right day, and the
# server needs no time zone database.
EASTERN = timezone(timedelta(hours=-4))


def as_list(value: Any) -> list[dict[str, Any]]:
    """Read an element that E*TRADE sends as one object or a list of them."""
    if value is None:
        return []
    if isinstance(value, dict):
        return [value]
    return list(value)


def decimal_at(data: dict[str, Any], key: str) -> Decimal | None:
    """Read a number as a Decimal, or None when it is missing or not a number."""
    value = data.get(key)
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except InvalidOperation:
        return None


def date_at(data: dict[str, Any], key: str) -> date | None:
    """Read a timestamp in epoch milliseconds as a date in US Eastern time, or
    None when it is missing or not a number."""
    value = data.get(key)
    if not str(value).isdigit():
        return None
    return datetime.fromtimestamp(int(str(value)) / 1000, EASTERN).date()
