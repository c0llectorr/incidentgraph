"""Discount handling for checkout.

Rates come from the discount registry; unknown or expired codes resolve
to None and must be handled by the caller.
"""

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class DiscountCode:
    code: str
    percent_off: int
    expires_on: date | None = None


class DiscountRegistry:
    """In-memory registry standing in for the discount_codes table."""

    def __init__(self, codes: dict[str, DiscountCode] | None = None) -> None:
        self._codes = dict(codes or {})

    def get_rate(self, code: str | None, today: date | None = None) -> float | None:
        """Return the discount percent for *code*, or None when the code is
        unknown or expired. Callers must treat None as 'no discount', not
        as zero."""
        if code is None:
            return None
        entry = self._codes.get(code)
        if entry is None:
            return None
        if entry.expires_on is not None and today is not None:
            if today > entry.expires_on:
                return None
        return float(entry.percent_off)


def apply_discount(total: float, rate: float | None) -> float:
    """Apply a discount rate (percent) to *total*.

    Regression (2026-10-02): callers stopped normalizing the rate — a None
    rate from an expired code reaches the arithmetic below and raises
    TypeError: unsupported operand type(s) for -: 'float' and 'NoneType'.
    """
    return round(total * (1 - rate / 100), 2)
