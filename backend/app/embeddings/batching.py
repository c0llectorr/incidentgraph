"""Bounded embedding batches with capped transient retries (PRD FR-15/§9.3).

Permanent failures are recorded explicitly as failed batches — never silently
skipped — so the pipeline can refuse to mark the index ready (§6.2).
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TypeVar

from app.core.retry import retry_transient

T = TypeVar("T")


@dataclass
class FailedBatch:
    start_index: int
    end_index: int
    error_code: str
    message: str


@dataclass
class BatchResult:
    vectors: list[list[float] | None] = field(default_factory=list)
    failures: list[FailedBatch] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.failures


def embed_in_batches(
    provider,
    texts: list[str],
    *,
    batch_size: int,
    max_retries: int = 4,
    is_transient: Callable[[Exception], bool] | None = None,
    sleep: Callable[[float], None] = time.sleep,
    on_batch_done: Callable[[int], None] | None = None,
) -> BatchResult:
    if batch_size <= 0:
        raise ValueError("batch_size must be positive")

    result = BatchResult(vectors=[None] * len(texts))
    for start in range(0, len(texts), batch_size):
        batch = texts[start : start + batch_size]
        try:
            vectors = retry_transient(
                lambda batch=batch: provider.embed_documents(batch),  # type: ignore[arg-type]
                is_transient=is_transient or _default_is_transient,
                max_retries=max_retries,
                base_delay_seconds=0.5,
                max_delay_seconds=8.0,
                sleep=sleep,
            )
        except Exception as exc:
            code = getattr(exc, "code", type(exc).__name__)
            result.failures.append(
                FailedBatch(
                    start_index=start,
                    end_index=start + len(batch) - 1,
                    error_code=str(code),
                    message=str(exc),
                )
            )
            continue
        for offset, vector in enumerate(vectors):
            result.vectors[start + offset] = vector
        if on_batch_done is not None:
            on_batch_done(len(batch))
    return result


def _default_is_transient(exc: Exception) -> bool:
    kind = type(exc).__name__.lower()
    if "timeout" in kind or "connection" in kind or "ratelimit" in kind.replace("_", ""):
        return True
    status = getattr(exc, "status_code", None) or getattr(exc, "http_status", None)
    if isinstance(status, int):
        return status in {408, 429, 500, 502, 503, 504}
    return bool(getattr(exc, "retryable", False))
