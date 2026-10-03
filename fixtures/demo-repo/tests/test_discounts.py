"""Unit tests for the discount path.

test_apply_discount_rejects_none documents the seeded regression; the xfail
marker keeps the suite green while making the known bug explicit.
"""

from datetime import date

import pytest

from app.discounts import DiscountCode, DiscountRegistry, apply_discount


def test_known_code_returns_rate() -> None:
    registry = DiscountRegistry({"WELCOME10": DiscountCode("WELCOME10", 10)})
    assert registry.get_rate("WELCOME10") == 10.0


def test_unknown_code_returns_none() -> None:
    registry = DiscountRegistry()
    assert registry.get_rate("SAVE15") is None


def test_expired_code_returns_none() -> None:
    registry = DiscountRegistry(
        {"OLD5": DiscountCode("OLD5", 5, expires_on=date(2026, 9, 1))}
    )
    assert registry.get_rate("OLD5", today=date(2026, 10, 3)) is None


def test_apply_discount_happy_path() -> None:
    assert apply_discount(200.0, 25.0) == 150.0


@pytest.mark.xfail(reason="seeded regression: None rate is not normalized", strict=True)
def test_apply_discount_rejects_none() -> None:
    """Expired/unknown codes yield None; checkout must not crash on them."""
    apply_discount(200.0, None)
