"""WP-9 gate: query rewriting, rank fusion, context budgeting, diversity."""

from __future__ import annotations

from app.domain.models import RetrievedChunk
from app.retrieval.context_builder import ContextBuilder
from app.retrieval.fusion import reciprocal_rank_fusion
from app.retrieval.query_rewriter import build_query_plan


def make_chunk(chunk_id, path, start=None, end=None, content="x"):
    return RetrievedChunk(
        chunk_id=chunk_id,
        repository_id="r",
        index_version="i",
        content=content,
        path=path,
        start_line=start,
        end_line=end,
    )


# --- query rewriter ----------------------------------------------------------


def test_identifiers_and_paths_extracted() -> None:
    plan = build_query_plan(
        "Which function creates database connections in app/db.py? Is it create_connection "
        "or DatabasePool? What raises ValueError on 'config'?"
    )
    assert "app/db.py" in plan.paths
    assert "create_connection" in plan.identifiers
    assert "DatabasePool" in plan.identifiers
    assert "ValueError" in plan.error_strings
    assert "config" in plan.quoted_phrases


def test_semantic_query_appends_identifiers() -> None:
    plan = build_query_plan("What calls the recommendation_service?")
    semantic = plan.semantic_query()
    assert "recommendation_service" in semantic
    assert semantic.startswith("What calls the recommendation_service?")


def test_lexical_patterns_bounded() -> None:
    question = " ".join(f"name_{i}" for i in range(40))
    plan = build_query_plan(question)
    assert len(plan.lexical_patterns()) <= 12


# --- fusion -------------------------------------------------------------------


def test_fusion_dedupes_and_ranks() -> None:
    dense = [make_chunk("a", "p1.py"), make_chunk("b", "p2.py"), make_chunk("c", "p3.py")]
    lexical = [make_chunk("b", "p2.py"), make_chunk("d", "p4.py")]
    fused = reciprocal_rank_fusion([dense, lexical])
    ids = [chunk.chunk_id for chunk in fused]
    assert len(ids) == len(set(ids)) == 4
    # 'b' appears in both lists → fused to the top.
    assert ids[0] == "b"


def test_fusion_single_list_preserves_order() -> None:
    dense = [make_chunk("a", "p.py"), make_chunk("b", "q.py")]
    fused = reciprocal_rank_fusion([dense])
    assert [chunk.chunk_id for chunk in fused] == ["a", "b"]


# --- context builder ------------------------------------------------------------


def test_budget_is_respected() -> None:
    builder = ContextBuilder(max_tokens=40)
    ranked = [make_chunk(f"c{i}", f"p{i}.py", content="word " * 20) for i in range(5)]
    bundle = builder.build(ranked)
    assert bundle.total_tokens <= 40
    assert bundle.truncated
    assert 1 <= len(bundle.chunks) < 5


def test_overlap_suppression_prefers_diversity() -> None:
    builder = ContextBuilder(max_tokens=10_000)
    ranked = [
        make_chunk("a", "app.py", start=1, end=50),
        make_chunk("b", "app.py", start=10, end=60),  # overlaps a → near-duplicate
        make_chunk("c", "other.py", start=1, end=10),
    ]
    bundle = builder.build(ranked)
    ids = [chunk.chunk_id for chunk in bundle.chunks]
    assert "a" in ids and "c" in ids
    # The overlapping chunk is deliberately suppressed (PRD FR-19: avoid
    # near-duplicates), not silently mixed in.
    assert "b" not in ids


def test_per_path_cap_forces_diversity() -> None:
    builder = ContextBuilder(max_tokens=10_000)
    ranked = [make_chunk(f"c{i}", "same.py", start=i * 100, end=i * 100 + 10) for i in range(8)]
    ranked += [make_chunk("z", "other.py", start=1, end=10)]
    bundle = builder.build(ranked)
    from_same = [chunk for chunk in bundle.chunks if chunk.path == "same.py"]
    assert len(from_same) <= 3  # _MAX_CHUNKS_PER_PATH in pass 1
    assert any(chunk.chunk_id == "z" for chunk in bundle.chunks)


def test_render_includes_source_metadata_for_citations() -> None:
    builder = ContextBuilder(max_tokens=1000)
    chunk = make_chunk("chk_abc", "app/auth.py", start=3, end=9, content="def authenticate(): ...")
    chunk = chunk.model_copy(update={"symbol_name": "authenticate"})
    bundle = builder.build([chunk])
    rendered = bundle.render()
    assert "[chk_abc]" in rendered
    assert "app/auth.py:3-9" in rendered
    assert "authenticate" in rendered
