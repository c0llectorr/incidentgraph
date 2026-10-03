"""Dense vector retrieval (PRD FR-17): top-k with mandatory repository and
index-version filters, source metadata on every chunk. Results below the
minimum similarity score are dropped so weak retrieval is detectable (FR-24)."""

from __future__ import annotations

from app.domain.models import RetrievedChunk
from app.retrieval.query_rewriter import QueryPlan


class DenseRetriever:
    def __init__(self, embedder, vector_store, top_k: int, min_score: float = 0.05) -> None:
        self._embedder = embedder
        self._vector_store = vector_store
        self._top_k = top_k
        self._min_score = min_score

    def retrieve(
        self, *, repository_id: str, index_version: str, plan: QueryPlan
    ) -> list[RetrievedChunk]:
        query_vector = self._embedder.embed_query(plan.semantic_query())
        results = self._vector_store.search(
            query_vector,
            repository_id=repository_id,
            index_version=index_version,
            top_k=self._top_k,
        )
        return [
            chunk
            for chunk in results
            if chunk.retrieval_score is None or chunk.retrieval_score >= self._min_score
        ]
