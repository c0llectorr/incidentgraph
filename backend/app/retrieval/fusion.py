"""Rank fusion with deduplication (PRD §10.1 step 5, FR-18).

Reciprocal-rank fusion: a chunk's fused score is the sum of 1/(k + rank)
across the lists it appears in. The same chunk never appears twice."""

from __future__ import annotations

from app.domain.models import RetrievedChunk

_K = 60


def reciprocal_rank_fusion(
    result_lists: list[list[RetrievedChunk]],
) -> list[RetrievedChunk]:
    scores: dict[str, float] = {}
    first_seen: dict[str, RetrievedChunk] = {}

    for results in result_lists:
        for rank, chunk in enumerate(results, start=1):
            scores[chunk.chunk_id] = scores.get(chunk.chunk_id, 0.0) + 1.0 / (_K + rank)
            first_seen.setdefault(chunk.chunk_id, chunk)

    ranked_ids = sorted(scores, key=lambda chunk_id: scores[chunk_id], reverse=True)
    fused: list[RetrievedChunk] = []
    for chunk_id in ranked_ids:
        chunk = first_seen[chunk_id]
        # Preserve the fused score so context building can reason about it.
        fused.append(chunk.model_copy(update={"retrieval_score": round(scores[chunk_id], 6)}))
    return fused
