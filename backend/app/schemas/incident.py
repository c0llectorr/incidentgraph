"""Incident schemas (PRD §8.5, FR-26..27). Missing values stay unknown —
the models never infer or default them (FR-26)."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.domain.models import Hypothesis, Signal, VerificationStep


class IncidentCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=8_000)
    affected_endpoint: str | None = None
    affected_service: str | None = None
    time_start: datetime | None = None
    time_end: datetime | None = None


class EvidenceIn(BaseModel):
    type: Literal["log", "traceback", "diff", "note"]
    content: str = Field(min_length=1, max_length=200_000)


class OutcomesIn(BaseModel):
    """A user-recorded verification result (PRD FR-36/FR-37). The app never
    executes checks itself; only users record outcomes."""

    step_id: str = Field(min_length=1)
    outcome: Literal["supports", "weakens", "inconclusive"] | None = None
    notes: str | None = Field(default=None, max_length=2_000)
    hypothesis_id: str | None = None
    hypothesis_status: Literal["supported", "weakened", "user_verified"] | None = None


class IncidentArtifactOut(BaseModel):
    artifact_id: str
    type: str
    size_bytes: int
    created_at: datetime | None = None


class IncidentOut(BaseModel):
    id: str
    repository_id: str
    index_version: str
    title: str
    description: str
    affected_endpoint: str | None = None
    affected_service: str | None = None
    time_start: datetime | None = None
    time_end: datetime | None = None
    normalized_signals: list[Signal] = Field(default_factory=list)
    verification_plan: list[VerificationStep] = Field(default_factory=list)
    evidence_gaps: list[str] = Field(default_factory=list)
    status: str
    created_at: datetime | None = None


class IncidentDetailOut(IncidentOut):
    artifacts: list[IncidentArtifactOut] = Field(default_factory=list)
    hypotheses: list[Hypothesis] = Field(default_factory=list)
