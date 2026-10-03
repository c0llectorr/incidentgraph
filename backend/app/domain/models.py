"""Provider-independent domain models (PRD §8.4 core data contracts).

SourceCitation, RetrievedChunk, and Hypothesis mirror the PRD contracts
exactly. These models never import API frameworks, persistence, or provider
SDKs (PRD §7.4 dependency direction).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.domain.enums import ChunkingMethod, ChunkType, EvidenceType

HypothesisStatus = Literal[
    "unverified", "supported", "weakened", "user_verified", "insufficient_evidence"
]


class SourceCitation(BaseModel):
    source_id: str
    path: str
    start_line: int | None = None
    end_line: int | None = None
    excerpt: str | None = None


class RetrievedChunk(BaseModel):
    chunk_id: str
    repository_id: str
    index_version: str
    content: str
    path: str
    start_line: int | None = None
    end_line: int | None = None
    symbol_name: str | None = None
    retrieval_score: float | None = None


class CodeChunk(BaseModel):
    """Internal chunk record with full FR-12 metadata."""

    chunk_id: str
    repository_id: str
    index_version: str
    path: str
    language: str
    chunk_type: ChunkType
    chunking_method: ChunkingMethod
    start_line: int
    end_line: int
    symbol_name: str | None = None
    parent_context: str | None = None
    content: str
    content_hash: str

    def to_retrieved(self, retrieval_score: float | None = None) -> RetrievedChunk:
        return RetrievedChunk(
            chunk_id=self.chunk_id,
            repository_id=self.repository_id,
            index_version=self.index_version,
            content=self.content,
            path=self.path,
            start_line=self.start_line,
            end_line=self.end_line,
            symbol_name=self.symbol_name,
            retrieval_score=retrieval_score,
        )


class VerificationStep(BaseModel):
    step_id: str
    description: str
    expected_if_supported: str
    expected_if_weakened: str
    # Filled only by the user (PRD FR-36: the app never executes checks).
    outcome: Literal["supports", "weakens", "inconclusive"] | None = None
    notes: str | None = None


class Hypothesis(BaseModel):
    hypothesis_id: str
    title: str
    explanation: str
    supporting_evidence: list[SourceCitation] = Field(default_factory=list)
    contradicting_evidence: list[SourceCitation] = Field(default_factory=list)
    missing_evidence: list[str] = Field(default_factory=list)
    verification_steps: list[str] = Field(default_factory=list)
    status: HypothesisStatus = "unverified"


class Signal(BaseModel):
    """Deterministically extracted incident signal (PRD FR-28)."""

    kind: str
    value: str
    file_path: str | None = None
    line_number: int | None = None
    detail: str | None = None


class IncidentSummary(BaseModel):
    incident_id: str
    repository_id: str
    index_version: str
    title: str
    description: str
    affected_endpoint: str | None = None
    affected_service: str | None = None
    time_start: datetime | None = None
    time_end: datetime | None = None


class WorkflowErrorRecord(BaseModel):
    node: str
    code: str
    message: str
    retryable: bool = False


class InvestigationReport(BaseModel):
    """Stable report schema (PRD FR-39/FR-40). Unknown fields stay None and
    are rendered as visibly unknown — never omitted or invented."""

    incident_id: str
    repository_id: str
    index_version: str
    title: str
    summary: str
    observed_facts: list[str] = Field(default_factory=list)
    model_interpretations: list[str] = Field(default_factory=list)
    user_verified_outcomes: list[str] = Field(default_factory=list)
    hypotheses: list[Hypothesis] = Field(default_factory=list)
    missing_evidence: list[str] = Field(default_factory=list)
    verification_plan: list[VerificationStep] = Field(default_factory=list)
    unresolved_questions: list[str] = Field(default_factory=list)
    evidence_gaps: list[str] = Field(default_factory=list)
    generated_at: datetime | None = None
    is_partial: bool = False
    postmortem: dict[str, Any] | None = None


class IncidentArtifactModel(BaseModel):
    artifact_id: str
    incident_id: str
    type: EvidenceType
    size_bytes: int
    created_at: datetime | None = None
