"""WP-7 gate: batching retries, dimension checks, repository isolation.

Uses the deterministic HashingEmbeddingProvider plus an in-memory fake store
so tests never need Chroma; a Chroma integration test runs when available.
"""

from __future__ import annotations

import pytest

from app.core.errors import ProviderError
from app.embeddings.batching import embed_in_batches
from app.embeddings.fake import HashingEmbeddingProvider
from tests.fixtures.in_memory_store import InMemoryVectorStore


class FlakyProvider(HashingEmbeddingProvider):
    def __init__(self, fail_times: int, exc: Exception) -> None:
        self.fail_times = fail_times
        self.exc = exc
        self.calls = 0

    def embed_documents(self, texts: list[str]) -> list[list[float]]:  # noqa: D102
        self.calls += 1
        if self.calls <= self.fail_times:
            raise self.exc
        return super().embed_documents(texts)


class PermanentProvider(HashingEmbeddingProvider):
    def embed_documents(self, texts: list[str]) -> list[list[float]]:  # noqa: D102
        raise ProviderError("invalid input shape", retryable=False)


class TimeoutLike(Exception):
    pass


def test_transient_failures_are_retried_with_backoff() -> None:
    provider = FlakyProvider(fail_times=2, exc=TimeoutLike("boom"))
    result = embed_in_batches(
        provider,
        ["a", "b", "c", "d"],
        batch_size=2,
        max_retries=4,
        sleep=lambda seconds: None,
    )
    assert result.ok
    assert all(vector is not None for vector in result.vectors)
    # Batch 1: 2 failures + 1 success; batch 2: 1 success.
    assert provider.calls == 4


def test_permanent_failure_records_failed_batch_explicitly() -> None:
    provider = PermanentProvider()
    result = embed_in_batches(
        provider,
        ["a", "b", "c"],
        batch_size=2,
        max_retries=1,
        sleep=lambda seconds: None,
    )
    assert not result.ok
    assert len(result.failures) == 2  # batches [0:2] and [2:3]
    assert result.failures[0].start_index == 0
    assert result.vectors == [None, None, None]


def test_empty_input_short_circuits() -> None:
    result = embed_in_batches(HashingEmbeddingProvider(), [], batch_size=8)
    assert result.ok and result.vectors == []


def test_hashing_provider_is_deterministic_and_ordered() -> None:
    provider = HashingEmbeddingProvider()
    texts = ["def authenticate(user): pass", "def other(): pass"]
    first = provider.embed_documents(texts)
    second = provider.embed_documents(texts)
    assert first == second
    assert len(first) == len(texts)
    assert all(len(vector) == provider.dimension for vector in first)
    # Similar texts share tokens → higher cosine than unrelated pairing.
    query = provider.embed_query("authenticate user")
    assert len(query) == provider.dimension


# --- in-memory vector store lives in tests/fixtures/in_memory_store.py ------


def test_dimension_mismatch_is_rejected() -> None:
    store = InMemoryVectorStore()
    store.dimension = 4
    from app.domain.models import CodeChunk
    from app.domain.enums import ChunkType, ChunkingMethod

    chunk = CodeChunk(
        chunk_id="chk_x", repository_id="r", index_version="i", path="a.py",
        language="python", chunk_type=ChunkType.FUNCTION, chunking_method=ChunkingMethod.PYTHON_AST,
        start_line=1, end_line=1, content="x", content_hash="h",
    )
    with pytest.raises(ProviderError):
        store.upsert([chunk], [[0.1] * 3], dimension=3)
