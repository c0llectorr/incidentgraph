"""Typed workflow state (PRD §11.2, FR-31).

Compact and JSON-able: no unbounded chat transcripts, no raw files."""

from __future__ import annotations

from typing import TypedDict


class InvestigationState(TypedDict, total=False):
    incident_id: str
    repository_id: str
    index_version: str
    incident_title: str
    incident_description: str
    incident_summary: str
    observed_facts: list[str]
    normalized_signals: list[dict]  # Signal dicts
    retrieved_evidence: list[dict]  # RetrievedChunk dicts
    hypotheses: list[dict]  # GeneratedHypothesis dicts
    verification_plan: list[dict]  # VerificationStep dicts
    evidence_gaps: list[str]
    review_notes: list[str]
    status: str
    errors: list[dict]  # WorkflowErrorRecord dicts
    resume: bool
    repair_attempted: bool
    has_evidence: bool
