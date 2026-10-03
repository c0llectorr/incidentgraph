"""Rate limiter behavior."""

from app.rate_limiter import RateLimiter


def test_allows_under_limit() -> None:
    limiter = RateLimiter(max_requests=3, window_seconds=60)
    assert all(limiter.allow("alice") for _ in range(3))


def test_blocks_over_limit() -> None:
    limiter = RateLimiter(max_requests=2, window_seconds=60)
    assert limiter.allow("bob")
    assert limiter.allow("bob")
    assert not limiter.allow("bob")
