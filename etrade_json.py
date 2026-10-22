"""
Reading values out of E*TRADE's JSON responses.

E*TRADE converts its XML responses to JSON, so an element that repeats becomes a
list only when it repeats: one account, position, or quote arrives as a bare
object.  Its numbers are JSON floats, which this server reads as Decimals.
"""

from decimal import Decimal, InvalidOperation
from typing import Any


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
