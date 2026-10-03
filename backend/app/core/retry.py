"""Capped exponential backoff with jitter for transient errors (PRD §6.2).

One shared policy for GitHub fetches, embedding batches, and model calls.
`sleep` is injectable so tests run instantly.
"""

from __future__ import annotations

import random
import time
from collections.abc import Callable
from typing import TypeVar

T = TypeVar("T")


def retry_transient(
    fn: Callable[[], T],
    *,
    is_transient: Callable[[Exception], bool],
    max_retries: int = 4,
    base_delay_seconds: float = 0.5,
    max_delay_seconds: float = 8.0,
    sleep: Callable[[float], None] = time.sleep,
    on_retry: Callable[[Exception, int, float], None] | None = None,
) -> T:
    """Run *fn*, retrying only while `is_transient(exc)` is true.

    Permanent (validation/auth/schema) errors propagate immediately —
    they are never retried indefinitely (PRD FR-15).
    """
    attempt = 0
    while True:
        try:
            return fn()
        except Exception as exc:  # noqa: BLE001 - classified by is_transient
            if not is_transient(exc) or attempt >= max_retries:
                raise
            delay = min(max_delay_seconds, base_delay_seconds * (2**attempt))
            delay = random.uniform(0.0, delay)  # jitter
            if on_retry is not None:
                on_retry(exc, attempt, delay)
            sleep(delay)
            attempt += 1
