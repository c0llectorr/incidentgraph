"""Lexical retrieval for exact identifiers, exception strings, and file names
(PRD FR-18, P1). Backed by SQL substring matching over chunk content/path."""

from __future__ import annotations

from app.domain.models import RetrievedChunk
from app.persistence.models import CodeChunkRow
from app.persistence.repositories import ChunkRepository
from app.persistence.unit_of_work import UnitOfWork
from app.retrieval.query_rewriter import QueryPlan


def _row_to_retrieved(row: CodeChunkRow) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=row.chunk_id,
        repository_id=row.repository_id,
        index_version=row.index_version,
        content=row.content,
        path=row.path,
        start_line=row.start_line,
        end_line=row.end_line,
        symbol_name=row.symbol_name,
        retrieval_score=None,
    )


class LexicalRetriever:
    def __init__(self, uow: UnitOfWork, top_k: int) -> None:
        self._uow = uow
        self._top_k = top_k

    def retrieve(
        self, *, repository_id: str, index_version: str, plan: QueryPlan
    ) -> list[RetrievedChunk]:
        patterns = plan.lexical_patterns()
        if not patterns:
            return []
        with self._uow.begin() as session:
            rows = ChunkRepository().search_lexical(
                session, repository_id, index_version, patterns, limit=self._top_k
            )
            return [_row_to_retrieved(row) for row in rows]
