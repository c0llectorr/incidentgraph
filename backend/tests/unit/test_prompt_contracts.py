"""Prompt ↔ schema pairing contract tests (PRD §14.3).

Each LLM system prompt declares a JSON response shape; the node that uses it
must parse against a schema that accepts exactly that shape. A mismatch here
is invisible to fake-model tests (the double returns schema instances
directly) and only explodes in production — as the normalize/review
QAAnswer mismatch did. This test extracts the JSON example from every prompt
and validates it against the paired schema.
"""

from __future__ import annotations

import json
import re

import pytest

from app.llm.output_parsers import (
    EvidenceReview,
    HypothesisSet,
    NormalizedIncident,
    QAAnswer,
)
from app.llm.prompts import (
    QA_SYSTEM_PROMPT,
    RCA_HYPOTHESES_SYSTEM_PROMPT,
    RCA_NORMALIZE_SYSTEM_PROMPT,
    RCA_REVIEW_SYSTEM_PROMPT,
)

_PAIRINGS = [
    (QA_SYSTEM_PROMPT, QAAnswer, "repository Q&A"),
    (RCA_NORMALIZE_SYSTEM_PROMPT, NormalizedIncident, "normalize_incident node"),
    (RCA_HYPOTHESES_SYSTEM_PROMPT, HypothesisSet, "generate_hypotheses node"),
    (RCA_REVIEW_SYSTEM_PROMPT, EvidenceReview, "review_evidence node"),
]


@pytest.mark.parametrize(("system_prompt", "schema", "label"), _PAIRINGS)
def test_prompt_example_validates_against_paired_schema(
    system_prompt: str, schema: type, label: str
) -> None:
    matches = re.findall(r"\{.*\}", system_prompt, re.DOTALL)
    assert matches, f"{label}: prompt declares no JSON response shape"
    example = json.loads(matches[-1])
    # Placeholder values ("string") satisfy str fields; required-field
    # mismatches are what this guard exists to catch.
    schema.model_validate(example)


def test_every_rca_prompt_has_a_registered_pairing() -> None:
    """No prompt may reach generate_structured without a contract entry."""
    from app.llm import prompts

    for name in dir(prompts):
        value = getattr(prompts, name)
        if isinstance(value, str) and value.endswith("}") and name.isupper():
            assert any(value is p for p, _, _ in _PAIRINGS), (
                f"prompt {name} has no prompt↔schema pairing registered"
            )
