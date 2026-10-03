"""Output validators for the RCA workflow (PRD FR-33/FR-34, §11.3).

Mechanical checks here; the LLM reviewer is a separate guardrail node."""

from __future__ import annotations

from app.domain.policies import validate_citations
from app.llm.output_parsers import HypothesisSet


def hypothesis_set_is_wellformed(hypotheses: HypothesisSet) -> bool:
    """FR-33: at most three hypotheses; each has explanation + verification."""
    if not 1 <= len(hypotheses.hypotheses) <= 3:
        return False
    for hypothesis in hypotheses.hypotheses:
        if not hypothesis.explanation.strip():
            return False
        if hypothesis.verification is None:
            return False
    return True


def cited_source_ids(hypotheses: HypothesisSet) -> list[str]:
    ids: list[str] = []
    for hypothesis in hypotheses.hypotheses:
        ids.extend(item.source_id for item in hypothesis.supporting)
        ids.extend(item.source_id for item in hypothesis.contradicting)
    return ids


def strip_invalid_citations(hypotheses: HypothesisSet, evidence_ids: set[str]) -> tuple[HypothesisSet, list[str]]:
    """Remove citations whose source IDs are not in the evidence set; return
    the cleaned set and the dropped IDs (conservative handling, FR-34)."""
    dropped: list[str] = []
    for hypothesis in hypotheses.hypotheses:
        for field_name in ("supporting", "contradicting"):
            items = getattr(hypothesis, field_name)
            kept = []
            for item in items:
                if item.source_id in evidence_ids:
                    kept.append(item)
                else:
                    dropped.append(item.source_id)
            setattr(hypothesis, field_name, kept)
    check = validate_citations(cited_source_ids(hypotheses), evidence_ids)
    assert not check.has_invalid
    return hypotheses, dropped


def hypotheses_with_valid_support(hypotheses: HypothesisSet) -> list[int]:
    """Indexes of hypotheses that retain at least one supporting citation."""
    return [
        index
        for index, hypothesis in enumerate(hypotheses.hypotheses)
        if hypothesis.supporting
    ]
