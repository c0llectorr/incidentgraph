"""In-memory VectorStore implementing the domain interface faithfully.

Used by the integration suite so tests run without Chroma; a separate
Chroma-backed test runs when chromadb is installed.
"""

from __future__ import annotations

from app.core.errors import ProviderError
from app.domain.models import CodeChunk, RetrievedChunk


class InMemoryVectorStore:
    def __init__(self) -> None:
        self._rows: dict[str, tuple[CodeChunk, list[float]]] = {}
        self.dimension: int | None = None

    def upsert(self, chunks: list[CodeChunk], vectors: list[list[float]], *, dimension: int) -> None:
        if self.dimension is None:
            self.dimension = dimension
        elif self.dimension != dimension:
            raise ProviderError("dimension mismatch")
        for chunk, vector in zip(chunks, vectors):
            self._rows[chunk.chunk_id] = (chunk, vector)

    def search(
        self,
        query_vector: list[float],
        *,
        repository_id: str,
        index_version: str,
        top_k: int,
    ) -> list[RetrievedChunk]:
        scored = []
        for chunk, vector in self._rows.values():
            if chunk.repository_id != repository_id or chunk.index_version != index_version:
                continue
            similarity = sum(a * b for a, b in zip(query_vector, vector))
            scored.append((similarity, chunk))
        scored.sort(key=lambda pair: pair[0], reverse=True)
        return [chunk.to_retrieved(round(score, 6)) for score, chunk in scored[:top_k]]

    def delete_by_repository(self, repository_id: str) -> int:
        doomed = [
            key
            for key, (chunk, _) in self._rows.items()
            if chunk.repository_id == repository_id
        ]
        for key in doomed:
            del self._rows[key]
        return len(doomed)

    def count(self, *, repository_id: str, index_version: str) -> int:
        return sum(
            1
            for chunk, _ in self._rows.values()
            if chunk.repository_id == repository_id and chunk.index_version == index_version
        )

    def get_vectors(self, chunk_ids: list[str]) -> dict[str, list[float]]:
        found: dict[str, list[float]] = {}
        for chunk_id in chunk_ids:
            row = self._rows.get(chunk_id)
            if row is not None:
                found[chunk_id] = row[1]
        return found
