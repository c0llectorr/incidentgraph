"""Integration tests against REAL Chroma (tmp persistence).

The in-memory VectorStore double cannot represent adapter-specific behaviors
(NumPy ndarray returns, None payloads) — this suite exercises the Chroma
adapter directly so adapter quirks surface in CI, not in production
ingestion runs.
"""

from __future__ import annotations

import pytest

from app.domain.enums import ChunkingMethod, ChunkType
from app.domain.models import CodeChunk
from app.vectorstore.chroma_store import ChromaVectorStore


@pytest.fixture()
def store(tmp_path) -> ChromaVectorStore:
    return ChromaVectorStore(tmp_path / "chroma-test")


def make_chunk(chunk_id: str, content: str) -> CodeChunk:
    return CodeChunk(
        chunk_id=chunk_id,
        repository_id="rep_test",
        index_version="idx_test",
        path=f"app/{chunk_id}.py",
        language="python",
        chunk_type=ChunkType.FUNCTION,
        chunking_method=ChunkingMethod.PYTHON_AST,
        start_line=1,
        end_line=3,
        content=content,
        content_hash=f"hash-{chunk_id}",
    )


def test_get_vectors_on_first_ingestion_returns_empty(store: ChromaVectorStore) -> None:
    """Regression: the exact production failure — no vectors stored yet, the
    collection returns a NumPy ndarray (or None) and the old `or []` idiom
    crashed on ndarray truthiness."""
    result = store.get_vectors(["chk_a", "chk_b", "chk_c"])
    assert result == {}


def test_get_vectors_empty_input_short_circuits(store: ChromaVectorStore) -> None:
    assert store.get_vectors([]) == {}


def test_get_vectors_returns_stored_vectors(store: ChromaVectorStore) -> None:
    chunks = [make_chunk("chk_a", "def authenticate(): pass"), make_chunk("chk_b", "def other(): pass")]
    store.upsert(chunks, [[0.5, 0.5], [0.1, 0.9]], dimension=2)

    result = store.get_vectors(["chk_a", "chk_b", "chk_missing"])
    assert set(result.keys()) == {"chk_a", "chk_b"}
    assert all(isinstance(value, list) for value in result.values())
    assert all(isinstance(component, float) for vector in result.values() for component in vector)


def test_upsert_search_count_round_trip(store: ChromaVectorStore) -> None:
    chunks = [make_chunk("chk_a", "auth code"), make_chunk("chk_b", "db code")]
    store.upsert(chunks, [[1.0, 0.0], [0.0, 1.0]], dimension=2)

    assert store.count(repository_id="rep_test", index_version="idx_test") == 2

    hits = store.search(
        [1.0, 0.0], repository_id="rep_test", index_version="idx_test", top_k=2
    )
    assert [chunk.chunk_id for chunk in hits][0] == "chk_a"
    assert all(isinstance(chunk.retrieval_score, float) for chunk in hits)

    # Repository isolation: another repository sees nothing.
    assert store.count(repository_id="rep_other", index_version="idx_test") == 0


def test_delete_by_repository_removes_vectors(store: ChromaVectorStore) -> None:
    chunks = [make_chunk("chk_a", "a"), make_chunk("chk_b", "b")]
    store.upsert(chunks, [[1.0, 0.0], [0.0, 1.0]], dimension=2)
    assert store.delete_by_repository("rep_test") == 2
    assert store.count(repository_id="rep_test", index_version="idx_test") == 0
