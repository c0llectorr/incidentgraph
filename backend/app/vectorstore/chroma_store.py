"""Chroma vector persistence adapter (PRD FR-16, §8.2 vectorstore/ row).

One persistent collection with mandatory repository/index-version metadata
filters on every operation — chunks are never mixed across repositories.
Other modules depend on the VectorStore interface, not this class.
"""

from __future__ import annotations

from pathlib import Path

from app.core.logging import get_logger
from app.domain.models import CodeChunk, RetrievedChunk

logger = get_logger(__name__)


class ChromaVectorStore:
    def __init__(self, persist_dir: Path, collection_name: str = "incidentgraph") -> None:
        import chromadb  # lazy: heavy import deferred until first use

        self._client = chromadb.PersistentClient(path=str(persist_dir))
        self._collection = self._client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},
        )
        self._dimension: int | None = None

    # -- VectorStore interface ----------------------------------------------

    def upsert(
        self,
        chunks: list[CodeChunk],
        vectors: list[list[float]],
        *,
        dimension: int,
    ) -> None:
        if not chunks:
            return
        if self._dimension is None:
            self._dimension = dimension
        elif self._dimension != dimension:
            from app.core.errors import ProviderError

            raise ProviderError(
                f"Vector dimension mismatch: store holds {self._dimension}, provider returned {dimension}."
            )
        self._collection.upsert(
            ids=[chunk.chunk_id for chunk in chunks],
            embeddings=vectors,
            documents=[chunk.content for chunk in chunks],
            metadatas=[
                {
                    "repository_id": chunk.repository_id,
                    "index_version": chunk.index_version,
                    "path": chunk.path,
                    "language": chunk.language,
                    "chunk_type": chunk.chunk_type.value,
                    "chunking_method": chunk.chunking_method.value,
                    "start_line": chunk.start_line,
                    "end_line": chunk.end_line,
                    "symbol_name": chunk.symbol_name or "",
                    "parent_context": chunk.parent_context or "",
                    "content_hash": chunk.content_hash,
                }
                for chunk in chunks
            ],
        )

    @staticmethod
    def _where(
        repository_id: str, index_version: str | None = None
    ) -> dict[str, object]:
        """Chroma requires explicit operators: a bare multi-key equality dict
        is rejected ("Expected where to have exactly one operator")."""
        conditions: list[dict[str, object]] = [{"repository_id": {"$eq": repository_id}}]
        if index_version is not None:
            conditions.append({"index_version": {"$eq": index_version}})
        if len(conditions) == 1:
            return conditions[0]
        return {"$and": conditions}

    def search(
        self,
        query_vector: list[float],
        *,
        repository_id: str,
        index_version: str,
        top_k: int,
    ) -> list[RetrievedChunk]:
        total = self.count(repository_id=repository_id, index_version=index_version)
        if total == 0:
            return []
        result = self._collection.query(
            query_embeddings=[query_vector],
            n_results=min(top_k, total),
            where=self._where(repository_id, index_version),
            include=["documents", "metadatas", "distances"],
        )
        chunks: list[RetrievedChunk] = []
        ids = result.get("ids", [[]])[0]
        documents = result.get("documents", [[]])[0]
        metadatas = result.get("metadatas", [[]])[0]
        distances = result.get("distances", [[]])[0]
        for chunk_id, document, metadata, distance in zip(ids, documents, metadatas, distances, strict=False):
            chunks.append(
                RetrievedChunk(
                    chunk_id=chunk_id,
                    repository_id=repository_id,
                    index_version=index_version,
                    content=document,
                    path=str(metadata.get("path", "")),
                    start_line=metadata.get("start_line"),
                    end_line=metadata.get("end_line"),
                    symbol_name=str(metadata.get("symbol_name")) or None,
                    retrieval_score=round(1.0 - float(distance), 6),
                )
            )
        return chunks

    def delete_by_repository(self, repository_id: str) -> int:
        existing = self._collection.get(where=self._where(repository_id), include=[])
        ids = list(existing.get("ids", []))
        if ids:
            self._collection.delete(ids=ids)
        return len(ids)

    def count(self, *, repository_id: str, index_version: str) -> int:
        existing = self._collection.get(
            where=self._where(repository_id, index_version),
            include=[],
        )
        return len(list(existing.get("ids", [])))

    def get_vectors(self, chunk_ids: list[str]) -> dict[str, list[float]]:
        if not chunk_ids:
            return {}
        found = self._collection.get(ids=chunk_ids, include=["embeddings"])
        # Chroma returns embeddings as a NumPy ndarray (or None when nothing
        # matches). Never evaluate it with `or` — ndarray truthiness is
        # ambiguous — handle None explicitly and iterate rows directly.
        embeddings = found.get("embeddings")
        if embeddings is None:
            return {}
        vectors: dict[str, list[float]] = {}
        ids = found.get("ids", [])
        for chunk_id, embedding in zip(ids, embeddings, strict=False):
            if embedding is not None:
                vectors[chunk_id] = [float(value) for value in embedding]
        return vectors
