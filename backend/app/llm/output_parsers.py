"""Structured LLM output contracts (PRD §8.4, §14.3).

Schema validation never replaces evidence validation (§14.3): these models
only make the shape checkable; the evidence validator (domain.policies) does
the rest."""

from __future__ import annotations

import json
import re

from pydantic import BaseModel, Field


class Claim(BaseModel):
    text: str
    source_ids: list[str] = Field(default_factory=list)


class QAAnswer(BaseModel):
    answer: str
    claims: list[Claim] = Field(default_factory=list)
    uncertainty: list[str] = Field(default_factory=list)
    insufficient_evidence: bool = False
    clarifying_question: str | None = None


class CitedEvidence(BaseModel):
    source_id: str
    note: str | None = None


class VerificationDraft(BaseModel):
    step: str
    expect_if_supported: str
    expect_if_weakened: str


class GeneratedHypothesis(BaseModel):
    title: str
    explanation: str
    supporting: list[CitedEvidence] = Field(default_factory=list)
    contradicting: list[CitedEvidence] = Field(default_factory=list)
    missing_evidence: list[str] = Field(default_factory=list)
    verification: VerificationDraft | None = None


class HypothesisSet(BaseModel):
    hypotheses: list[GeneratedHypothesis] = Field(default_factory=list)


_JSON_BLOCK = re.compile(r"\{.*\}", re.DOTALL)


def extract_json(text: str) -> str:
    """Best-effort JSON extraction: direct parse first, then the outermost
    braces (some models wrap JSON in prose or fences)."""
    try:
        json.loads(text)
        return text
    except (json.JSONDecodeError, ValueError):
        pass
    match = _JSON_BLOCK.search(text)
    if match:
        return match.group(0)
    raise ValueError("Model output contained no JSON object.")


def parse_structured(text: str, schema: type[BaseModel]):
    return schema.model_validate_json(extract_json(text))
