"""Dense vector retrieval (PRD FR-17): top-k with mandatory repository and
index-version filters, source metadata on every chunk."""

from __future__ import annotations

from app.retrieval.query_rewriter import QueryPlan


class DenseRetriever:
    def __init__(self, embedder, vector_store, top_k: int) -> None:
        self._embedder = embedder
        self._vector_store = vector_store
        self._top_k = top_k

    def retrieve(
        self, *, repository_id: str, index_version: str, plan: QueryPlan
    ) -> list:
        query_vector = self._embedder.embed_query(plan.semantic_query())
        return self._vector_store.search(
            query_vector,
            repository_id=repository_id,
            index_version=index_version,
            top_k=self._top_k,
        )
