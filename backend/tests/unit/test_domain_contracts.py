"""WP-2 gate: domain contracts, status-transition policy, citation validation."""

from __future__ import annotations

import pytest
from pydantic import ValidationError as PydanticValidationError

from app.domain.enums import IngestionStage
from app.domain.models import Hypothesis, RetrievedChunk, SourceCitation
from app.domain.policies import (
    STAGE_WEIGHTS,
    can_transition,
    estimate_tokens,
    validate_citations,
)


def test_source_citation_round_trip() -> None:
    citation = SourceCitation(source_id="chk_abc", path="app/main.py", start_line=10, end_line=20)
    assert SourceCitation.model_validate_json(citation.model_dump_json()) == citation


def test_retrieved_chunk_defaults_match_prd() -> None:
    chunk = RetrievedChunk(
        chunk_id="chk_1",
        repository_id="rep_1",
        index_version="idx_1",
        content="def main(): pass",
        path="app/main.py",
    )
    assert chunk.start_line is None
    assert chunk.symbol_name is None
    assert chunk.retrieval_score is None


def test_hypothesis_status_is_qualitative_enum() -> None:
    hypothesis = Hypothesis(hypothesis_id="hyp_1", title="t", explanation="e")
    assert hypothesis.status == "unverified"
    with pytest.raises(PydanticValidationError):
        Hypothesis(
            hypothesis_id="hyp_2",
            title="t",
            explanation="e",
            status=0.87,  # type: ignore[arg-type]
        )


@pytest.mark.parametrize(
    ("old", "new", "expected"),
    [
        ("unverified", "supported", True),
        ("unverified", "insufficient_evidence", True),
        ("supported", "user_verified", True),
        ("weakened", "supported", True),
        ("user_verified", "weakened", False),  # terminal
        ("user_verified", "supported", False),  # terminal
        ("insufficient_evidence", "user_verified", False),  # must pass through evidence first
    ],
)
def test_hypothesis_transition_policy(old: str, new: str, expected: bool) -> None:
    assert can_transition(old, new) is expected  # type: ignore[arg-type]


def test_stage_weights_cover_all_stages_and_sum_below_one() -> None:
    assert set(STAGE_WEIGHTS) == {
        IngestionStage.VALIDATING_SOURCE,
        IngestionStage.FETCHING_REPOSITORY,
        IngestionStage.EXTRACTING_FILES,
        IngestionStage.FILTERING_FILES,
        IngestionStage.PARSING_AND_CHUNKING,
        IngestionStage.EMBEDDING,
        IngestionStage.PERSISTING_INDEX,
        IngestionStage.VERIFYING_INDEX,
    }
    assert sum(STAGE_WEIGHTS.values()) == pytest.approx(1.0)


def test_validate_citations_rejects_fabricated_ids() -> None:
    evidence = {"chk_a", "chk_b"}
    check = validate_citations(["chk_a", "chk_fabricated"], evidence)
    assert check.valid_ids == ("chk_a",)
    assert check.invalid_ids == ("chk_fabricated",)
    assert check.has_invalid


def test_estimate_tokens_is_positive_and_monotonic() -> None:
    assert estimate_tokens("") >= 1
    assert estimate_tokens("abcd") >= 1
    assert estimate_tokens("a" * 400) > estimate_tokens("a" * 40)
